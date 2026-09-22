import json
import yaml
import csv
import warnings
from typing import Any

from agents.agents import AgentType
from agents.models import AttributeType

def prompt_int(prompt="> "):
    while True:
        raw = input(prompt).strip()
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")

def prompt_optional_int(prompt="> ") -> int | None:
    """Prompt for an int, or None if the user leaves the line blank.

    Unlike prompt_int, an empty response is a valid answer here (it
    means "no value") rather than something to keep re-prompting for.
    Used for S-11's optional seed field — leaving it blank means the
    simulation is unseeded (non-reproducible), not a validation error.
    """
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return None
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number, or leave blank for no seed.")

def prompt_float(prompt="> "):
    while True:
        raw = input(prompt).strip()
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")

def prompt_yes_no(prompt="> "):
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please enter y or n.")

def prompt_choice(prompt, choices):
    """Prompt until the user enters one of `choices` (case-insensitive).
    Returns the matching entry from `choices`, preserving its original case."""
    lowered = {c.lower(): c for c in choices}
    while True:
        raw = input(prompt).strip().lower()
        if raw in lowered:
            return lowered[raw]
        print(f"Please enter one of: {', '.join(choices)}")

# Export and import

def agent_type_to_json(agent_type: AgentType) -> str:
    return agent_type.model_dump_json(indent=2)


def agent_type_from_json(data: str) -> AgentType:
    return AgentType.model_validate_json(data)


def agent_type_to_yaml(agent_type: AgentType) -> str:
    return yaml.safe_dump(agent_type.model_dump(mode="json"), sort_keys=False)


def agent_type_from_yaml(data: str) -> AgentType:
    return AgentType.model_validate(yaml.safe_load(data))

def import_csv(csv_path: str, agent_type: AgentType) -> list[dict[str, Any]]:
    """Parse a CSV of literal initial agent attribute values for one agent type.

    Column headers are matched against agent_type's attribute names.
    Columns not found in agent_type.attributes are ignored, with a warning
    (per-column, not per-row, to avoid noisy repeated warnings).

    Row count vs agent_type.count:
        - More rows than count: only the first `count` rows are kept
          (row order preserved), a warning names how many were dropped.
        - Fewer rows than count: all rows are kept as-is; from_config()
          is responsible for generating the remaining agents normally.
          A warning is issued here so the shortfall is visible at parse
          time, not just downstream.

    Every recognised column must be present and non-empty in every row
    kept — a row missing a required attribute is rejected with a
    ValueError naming the row and the missing column(s), rather than
    silently falling back to generation for just that attribute.

    Args:
        csv_path: path to the CSV file.
        agent_type: the AgentType whose attribute schema and count govern
            how columns are matched and how many rows are kept.

    Returns:
        A list of dicts, one per row kept, each mapping attribute name to
        its coerced Python value (int/float/bool/str per the attribute's
        AttributeType). Length is min(number of CSV rows, agent_type.count).

    Raises:
        ValueError: a kept row is missing a required column, or a value
            fails to coerce to its attribute's declared type.
        FileNotFoundError: csv_path does not exist.
    """
    known_attrs = {a.name: a.type for a in agent_type.attributes}

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        unrecognised = [name for name in fieldnames if name not in known_attrs]
        for name in unrecognised:
            warnings.warn(
                f"agent type '{agent_type.name}': CSV column '{name}' does not "
                f"match any known attribute — ignoring this column."
            )

        recognised_columns = [name for name in fieldnames if name in known_attrs]
        rows = list(reader)

    if len(rows) > agent_type.count:
        warnings.warn(
            f"agent type '{agent_type.name}': CSV has {len(rows)} rows, only "
            f"{agent_type.count} expected — keeping the first {agent_type.count}, "
            f"ignoring the remaining {len(rows) - agent_type.count}."
        )
    elif len(rows) < agent_type.count:
        warnings.warn(
            f"agent type '{agent_type.name}': CSV has only {len(rows)} rows, "
            f"{agent_type.count} expected — the remaining "
            f"{agent_type.count - len(rows)} will be generated normally."
        )

    kept_rows = rows[: agent_type.count]

    records: list[dict[str, Any]] = []
    for i, row in enumerate(kept_rows):
        record: dict[str, Any] = {}
        missing = []
        for name in recognised_columns:
            raw = row.get(name)
            if raw is None or raw == "":
                missing.append(name)
                continue
            record[name] = _coerce(raw, known_attrs[name], name, i)
        if missing:
            raise ValueError(
                f"agent type '{agent_type.name}': CSV row {i} is missing "
                f"required column(s): {missing}"
            )
        records.append(record)

    return records


def _coerce(raw: str, attr_type: AttributeType, column: str, row_index: int) -> Any:
    """Coerce a raw CSV string to the attribute's declared Python type."""
    try:
        if attr_type == AttributeType.INT:
            return int(raw)
        if attr_type == AttributeType.FLOAT:
            return float(raw)
        if attr_type == AttributeType.BOOL:
            lowered = raw.strip().lower()
            if lowered in ("true", "1"):
                return True
            if lowered in ("false", "0"):
                return False
            raise ValueError(f"unrecognised boolean value '{raw}'")
        return raw  # CATEGORICAL — kept as string
    except ValueError as exc:
        raise ValueError(
            f"CSV row {row_index}, column '{column}': cannot coerce "
            f"'{raw}' to {attr_type.value} — {exc}"
        ) from exc