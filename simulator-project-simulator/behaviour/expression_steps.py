"""
Multi-assignment structure for conditional rules.

A rule entry is a list of steps. Each step is either an assignment
({"field", "expression", "topology_name"?}) or a conditional
({"condition", "then", "else"}), mirroring a sequence of Python statements.
"""
from __future__ import annotations

import ast
import logging
from typing import Any, Iterable, Iterator, Mapping, Union

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, TypeAdapter, field_validator, model_serializer

logger = logging.getLogger("simulator")

# TODO: import from the Ticket 3 module instead of redefining here.
NEIGHBOUR_HELPERS: frozenset[str] = frozenset(
    {"neighbor_count", "neighbor_mean"}  # add the rest of Ticket 3's fixed set
)

# Soft threshold for else-nesting; warn above it, never block evaluation.
# Reuse the same constant/mechanism as Ticket 2 if one exists.
SOFT_ELSE_DEPTH = 5


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class AssignmentStep(BaseModel):
    """A single field assignment: ``state[field] = eval(expression)``."""

    model_config = ConfigDict(extra="forbid")

    field: str
    expression: str
    topology_name: str | None = None

    @field_validator("expression")
    @classmethod
    def _expression_parses(cls, value: str) -> str:
        """Reject expressions that are not valid Python expressions."""
        try:
            ast.parse(value, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"invalid expression {value!r}: {exc.msg}") from exc
        return value


class ConditionalRule(BaseModel):
    """``if condition: then-steps else: else-steps`` (else may nest)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    condition: str
    then: list["RuleStep"]
    else_: list["RuleStep"] = Field(default_factory=list, alias="else")
    topology_name: str | None = None  # needed only if the condition calls a helper

    @model_serializer(mode="wrap")
    def _dump_else_key(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Rename `else_` to `else` in every dump, with or without by_alias."""
        data = handler(self)
        if "else_" in data:
            data["else"] = data.pop("else_")
        return data


RuleStep = Union[AssignmentStep, ConditionalRule]
ConditionalRule.model_rebuild()
_STEPS_ADAPTER: TypeAdapter[list[RuleStep]] = TypeAdapter(list[RuleStep])


# --------------------------------------------------------------------------
# Step-splitting (authored line -> {field, expression})
# --------------------------------------------------------------------------
def _target_field(target: ast.expr) -> str:
    """Return the field name from ``age`` or ``state['age']`` targets."""
    if isinstance(target, ast.Name):
        return target.id
    if (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and target.value.id == "state"
        and isinstance(target.slice, ast.Constant)
        and isinstance(target.slice.value, str)
    ):
        return target.slice.value
    raise ValueError("assignment target must be a field name or state['field']")


def desugar_line(line: str) -> dict[str, str]:
    """Desugar one authored assignment / augmented assignment line.

    ``"age += 1"`` -> ``{"field": "age", "expression": "state['age'] + 1"}``
    simpleeval only evaluates expressions, so statements are split here.
    """
    body = ast.parse(line.strip(), mode="exec").body
    if len(body) != 1:
        raise ValueError(f"expected exactly one statement, got {len(body)}: {line!r}")
    node = body[0]

    if isinstance(node, ast.Assign):
        if len(node.targets) != 1:
            raise ValueError(f"chained assignment not supported: {line!r}")
        field, value = _target_field(node.targets[0]), node.value
    elif isinstance(node, ast.AugAssign):
        field = _target_field(node.target)
        current = ast.Subscript(
            value=ast.Name(id="state", ctx=ast.Load()),
            slice=ast.Constant(value=field),
            ctx=ast.Load(),
        )
        value = ast.BinOp(left=current, op=node.op, right=node.value)
    else:
        raise ValueError(f"only assignments are allowed, got: {line!r}")

    return {"field": field, "expression": ast.unparse(value)}


def normalise_steps(raw: Iterable[Any]) -> list[Any]:
    """Recursively desugar authored string lines into step dicts."""
    out: list[Any] = []
    for item in raw:
        if isinstance(item, str):
            out.append(desugar_line(item))
        elif isinstance(item, Mapping) and "condition" in item:
            else_raw = item.get("else", item.get("else_", []))
            rest = {k: v for k, v in item.items() if k not in ("else", "else_")}
            out.append(
                {
                    **rest,
                    "then": normalise_steps(item.get("then", [])),
                    "else": normalise_steps(else_raw),
                }
            )
        else:
            out.append(item)
    return out


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def walk_steps(steps: list[RuleStep]) -> Iterator[tuple[RuleStep, int]]:
    """Yield ``(step, else_depth)`` iteratively, so there is no depth cap."""
    stack: list[tuple[RuleStep, int]] = [(s, 0) for s in steps]
    while stack:
        step, depth = stack.pop()
        yield step, depth
        if isinstance(step, ConditionalRule):
            stack.extend((s, depth) for s in step.then)
            stack.extend((s, depth + 1) for s in step.else_)


def calls_neighbour_helper(expression: str) -> bool:
    """True if the expression calls a neighbour helper or reads `neighbours`.

    Detected by AST inspection, not substring matching: a Call to a name in
    NEIGHBOUR_HELPERS, or a bare reference to the name `neighbours`.
    """
    for node in ast.walk(ast.parse(expression, mode="eval")):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in NEIGHBOUR_HELPERS
        ):
            return True
        if isinstance(node, ast.Name) and node.id == "neighbours":
            return True
    return False


def _check_topology(
    expression: str,
    topology_name: str | None,
    label: str,
    topology_names: list[str],
) -> None:
    """Apply the topology_name rules to one expression (step or condition).

    Args:
        expression: the expression text to inspect for neighbour-helper calls.
        topology_name: the name given on the step/conditional, if any.
        label: text identifying the step in error messages.
        topology_names: names of all configured topologies.

    Raises:
        ValueError: if a name is required but missing, or names an unknown topology.
    """
    if (
        len(topology_names) >= 2
        and topology_name is None
        and calls_neighbour_helper(expression)
    ):
        raise ValueError(
            f"{label} uses a neighbour helper but has no topology_name; "
            f"required with {len(topology_names)} topologies"
        )
    if topology_name is not None and topology_names and topology_name not in topology_names:
        raise ValueError(f"{label} has unknown topology_name {topology_name!r}")


def validate_steps(steps: list[RuleStep], topology_names: list[str]) -> None:
    """Config-build validation: topology_name rules + soft nesting warning."""
    warned = False
    for step, else_depth in walk_steps(steps):
        if isinstance(step, ConditionalRule):
            if else_depth > SOFT_ELSE_DEPTH and not warned:
                logger.warning(
                    "else-nesting depth %d exceeds soft limit %d; "
                    "consider flattening the rule",
                    else_depth, SOFT_ELSE_DEPTH,
                )
                warned = True
            _check_topology(
                step.condition, step.topology_name,
                f"condition {step.condition!r}", topology_names,
            )
        else:
            _check_topology(
                step.expression, step.topology_name,
                f"step for field {step.field!r}", topology_names,
            )


def build_rule_steps(raw: Any, topology_names: list[str]) -> list[RuleStep]:
    """Parse + validate a rule entry. Legacy single dict -> one-step list."""
    if isinstance(raw, Mapping):  # existing single-expression rules, no migration
        raw = [raw]
    steps = _STEPS_ADAPTER.validate_python(normalise_steps(raw))
    validate_steps(steps, topology_names)
    return steps
