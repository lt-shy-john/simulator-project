"""Aggregate Stats Collector (S-09).

Defines collectors in config as {name, type: count|mean|sum, filter_expr, attr},
evaluates them against the model's restricted aggregate proxy (model.count/
mean/sum, same simpleeval sandbox as S-10 stopping conditions), and produces
one wide dict per step: {step, agent_count, <collector_name>: value, ...}.
"""
from dataclasses import dataclass
from typing import Any, Literal


RESERVED_COLUMN_NAMES = {"step", "agent_count"}


@dataclass
class AggregateCollectorConfig:
    """One user-defined collector, as parsed from config."""
    name: str
    type: Literal["count", "mean", "sum"]
    filter_expr: str
    attr: str | None = None


class AggregateConfigError(ValueError):
    """Raised when the aggregates config section is invalid."""


def compile_aggregates(config: dict[str, Any]) -> list[AggregateCollectorConfig]:
    """Parse and validate the 'aggregates' config section.

    Raises:
        AggregateConfigError: on a name collision (with another collector
            or a reserved column name), a missing filter_expr, or a
            missing attr on a mean/sum collector.
    """
    raw_collectors = config.get("aggregates", [])
    collectors: list[AggregateCollectorConfig] = []
    seen_names: set[str] = set()

    for raw in raw_collectors:
        name = raw.get("name")
        collector_type = raw.get("type")
        filter_expr = raw.get("filter_expr")
        attr = raw.get("attr")

        if not name:
            raise AggregateConfigError("Aggregate collector missing required 'name'.")
        if name in RESERVED_COLUMN_NAMES:
            raise AggregateConfigError(
                f"Aggregate collector name '{name}' collides with a reserved "
                f"column name {RESERVED_COLUMN_NAMES}."
            )
        if name in seen_names:
            raise AggregateConfigError(f"Duplicate aggregate collector name: '{name}'.")
        if not filter_expr:
            raise AggregateConfigError(f"Aggregate collector '{name}' missing required 'filter_expr'.")
        if collector_type not in ("count", "mean", "sum"):
            raise AggregateConfigError(
                f"Aggregate collector '{name}' has invalid type '{collector_type}' "
                f"(must be count, mean, or sum)."
            )
        if collector_type in ("mean", "sum") and not attr:
            raise AggregateConfigError(
                f"Aggregate collector '{name}' of type '{collector_type}' requires 'attr'."
            )

        seen_names.add(name)
        collectors.append(AggregateCollectorConfig(
            name=name, type=collector_type, filter_expr=filter_expr, attr=attr,
        ))

    return collectors


def _agent_count_by_type(model) -> dict[str, int]:
    """Built-in collector: count of live agents per agent_type_name."""
    counts: dict[str, int] = {}
    for agent in model.agents:
        counts[agent.agent_type_name] = counts.get(agent.agent_type_name, 0) + 1
    return counts


def collect_aggregates(model, collectors: list[AggregateCollectorConfig]) -> dict[str, Any]:
    """Evaluate all collectors against the model's current state and
    return one wide row for this step: {step, agent_count, <name>: value, ...}.

    Called at end-of-step, after lifecycle events are applied - same
    point stopping conditions are checked and step_end is logged.
    """
    row: dict[str, Any] = {
        "step": model.step,
        "agent_count": _agent_count_by_type(model),
    }

    for collector in collectors:
        if collector.type == "count":
            value = model.count(collector.filter_expr)
        elif collector.type == "mean":
            value = model.mean(collector.attr, collector.filter_expr)
        else:  # "sum"
            value = model.sum(collector.attr, collector.filter_expr)
        row[collector.name] = value

    return row