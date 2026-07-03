# Step 1: Agent

## Purpose

This document covers the **Agent** element — step 1 of the Structure
group in the wizard (see `abm-wizard-framework.md` for how this fits into
the full 11-element design). It describes the data model, validation
rules, serialisation format, how to use it, and troubleshooting guidance.

**Audience:** maintainers working on the Agent model, the wizard steps
that drive it, or anything that consumes/produces `AgentType` data
(CLI, web backend, simulation runner).

**Status:** implemented. Draft models, not yet wired into the runner.

---

## Scope

**In scope for this step:**

- Multiple agent types, each with a name and count
- Attribute definitions: name, type, distribution
- Homogeneous vs. heterogeneous generation
- For heterogeneous types: per-attribute population via distribution,
  manual entry, or bulk upload
- JSON/YAML round-trip
- Validation (e.g. negative counts, unknown distribution types)

**Explicitly out of scope for this step:**

- Actually reading/merging an uploaded CSV/Excel file back into an agent
  type (bulk upload is tracked as a pending template handoff only — see
  below)
- The full simulation `Settings` object — `AgentType` is one element of
  it, not the whole config

---

## Data model

### Enums

| Enum | Values | Notes |
|---|---|---|
| `AttributeType` | `int`, `float`, `bool`, `categorical` | The declared type of an attribute |
| `GenerationMode` | `homogeneous`, `heterogeneous` | Whether all agents of this type share identical attribute values |
| `PopulationMethod` | `distribution`, `manual`, `bulk_upload` | How a heterogeneous attribute's values get filled in |
| `PopulationStatus` | `not_configured`, `schema_only`, `pending_import`, `complete` | Derived wizard-menu status (see below) — not stored, computed |

### Distribution specs

Distributions are a **discriminated union** keyed on a `kind` field, so
JSON/YAML round-trips are unambiguous and unknown/malformed distribution
types are rejected by validation rather than silently accepted as an
arbitrary dict.

| Kind | Fields | Purpose |
|---|---|---|
| `fixed` | `value` | Same value for every agent |
| `uniform` | `low`, `high` | Uniform range |
| `normal` | `mean`, `stddev` | Normal distribution |
| `categorical` | `weights` (dict of label → weight) | Weighted categorical draw |

### `AttributeDefinition`

- `name: str`
- `type: AttributeType`
- `population_method: PopulationMethod | None` — `None` means the
  attribute's schema is defined but not yet populated (this is what
  produces `SCHEMA_ONLY` status at the `AgentType` level)
- `distribution: Distribution | None` — only set when
  `population_method` is `distribution`

### `AgentType`

- `name: str`
- `count: int`
- `generation_mode: GenerationMode`
- `attributes: list[AttributeDefinition]`
- `bulk_upload_template_path: str | None` — only meaningful when
  heterogeneous and at least one attribute uses `bulk_upload`; tracks the
  template/import handoff without this model needing to know anything
  about file I/O
- `status` (property, derived — see below)

---

## Status derivation

`AgentType.status` is **computed, not stored**, to avoid it drifting out
of sync with the actual attribute data. Logic, in order:

1. No attributes defined → `NOT_CONFIGURED`
2. `HOMOGENEOUS` mode with attributes defined → `COMPLETE`
   (schema *is* the values, so there's nothing further to populate)
3. `HETEROGENEOUS` mode:
   - If any attribute uses `bulk_upload`:
     - No template written yet (`bulk_upload_template_path is None`) →
       `SCHEMA_ONLY`
     - Template written, not yet loaded back → `PENDING_IMPORT`
   - Else, if every attribute has a `population_method` set → `COMPLETE`
   - Otherwise → `SCHEMA_ONLY`

This is the field that should back menu tags like "[not configured]",
"[2 types defined]", or "pending import" in either wizard renderer.

---

## Validation rules

All of the following raise `pydantic.ValidationError` at construction
time:

| Rule | Where | Message pattern |
|---|---|---|
| `count >= 0` | `AgentType` | `agent type '<name>': count must be >= 0, got <count>` |
| No duplicate attribute names within an agent type | `AgentType` | `agent type '<name>': duplicate attribute names: [...]` |
| `uniform.low <= uniform.high` | `UniformDistribution` | `uniform distribution: low (<low>) must be <= high (<high>)` |
| `normal.stddev >= 0` | `NormalDistribution` | `normal distribution: stddev must be >= 0, got <stddev>` |
| `categorical.weights` non-empty | `CategoricalDistribution` | `categorical distribution: weights must not be empty` |
| `categorical.weights` values `>= 0` | `CategoricalDistribution` | `categorical distribution: weights must be >= 0` |
| `distribution` set **iff** `population_method == distribution` | `AttributeDefinition` | Either: `population_method is 'distribution' but no distribution is set`, or: `distribution is set but population_method is '<method>'` |
| Unknown `kind` value on a distribution | discriminated union | Standard Pydantic discriminator error — the value doesn't match any of `fixed` / `uniform` / `normal` / `categorical` |

---

## JSON / YAML round-trip

Four helper functions:

- `agent_type_to_json(agent_type) -> str`
- `agent_type_from_json(data: str) -> AgentType`
- `agent_type_to_yaml(agent_type) -> str`
- `agent_type_from_yaml(data: str) -> AgentType`

**Purpose:** a user can export an `AgentType` (or a set of them) to YAML
for reuse across sessions/projects, and import a YAML file to set it as
an agent type spec directly — this is the mechanism behind "load a saved
agent config" in both the CLI and web wizard, and behind draft
save/resume.

---

## How to use

### Homogeneous agent type

```python
from agent_model import AgentType, AttributeDefinition, AttributeType, GenerationMode

agent = AgentType(
    name="Citizen",
    count=100,
    generation_mode=GenerationMode.HOMOGENEOUS,
    attributes=[
        AttributeDefinition(name="susceptible", type=AttributeType.BOOL),
    ],
)

print(agent.status)  # PopulationStatus.COMPLETE
```

### Heterogeneous agent type, populated via distribution

```python
from agent_model import (
    AgentType, AttributeDefinition, AttributeType, GenerationMode,
    PopulationMethod, NormalDistribution,
)

agent = AgentType(
    name="Citizen",
    count=100,
    generation_mode=GenerationMode.HETEROGENEOUS,
    attributes=[
        AttributeDefinition(
            name="age",
            type=AttributeType.INT,
            population_method=PopulationMethod.DISTRIBUTION,
            distribution=NormalDistribution(mean=40, stddev=12),
        ),
    ],
)

print(agent.status)  # PopulationStatus.COMPLETE
```

### Heterogeneous agent type, pending bulk upload

```python
agent = AgentType(
    name="Citizen",
    count=100,
    generation_mode=GenerationMode.HETEROGENEOUS,
    attributes=[
        AttributeDefinition(
            name="income",
            type=AttributeType.FLOAT,
            population_method=PopulationMethod.BULK_UPLOAD,
        ),
    ],
)

print(agent.status)  # PopulationStatus.SCHEMA_ONLY

agent.bulk_upload_template_path = "/tmp/citizen_income_template.csv"
print(agent.status)  # PopulationStatus.PENDING_IMPORT
```

### Export / import as YAML

```python
from agent_model import agent_type_to_yaml, agent_type_from_yaml

yaml_str = agent_type_to_yaml(agent)
# ... save yaml_str to disk, or hand to the CLI/web wizard for reuse ...

restored = agent_type_from_yaml(yaml_str)
assert restored == agent
```

---

## Troubleshooting

**"Field required" / discriminator error when loading a distribution
from YAML or JSON**
The `kind` field on a distribution (`fixed` / `uniform` / `normal` /
`categorical`) must be present and must match one of the four supported
values exactly. This usually happens when a YAML file was hand-edited and
`kind` was omitted, misspelled, or left as a value from an older schema
version.

**"distribution is set but population_method is '...'"**
An `AttributeDefinition` had a `distribution` supplied without
`population_method` set to `distribution` (or vice versa — `distribution`
missing while `population_method` is `distribution`). These two fields
must agree; there's no implicit inference between them. Check both fields
are set together when constructing or hand-editing a config.

**Status stuck at `SCHEMA_ONLY` when it looks "done"**
For heterogeneous agent types, `COMPLETE` requires *every* attribute to
have a `population_method` set — a single attribute left at `None`
(schema defined, not yet populated) will hold the whole agent type at
`SCHEMA_ONLY`. Check all attributes, not just the ones the user most
recently edited.

**Status stuck at `SCHEMA_ONLY` / `PENDING_IMPORT` even though a file
was uploaded**
`bulk_upload_template_path` only tracks that a *template* was generated —
it does not track whether the filled-in file has been re-imported. Since
reading the uploaded file back into the model is out of scope for this
step, `PENDING_IMPORT` is the correct terminal state until the
CSV-merge step (tracked separately) exists. This is expected behaviour,
not a bug, but is worth surfacing clearly in the UI so users don't think
the wizard is stuck.

**"uniform distribution: low (...) must be <= high (...)"**
`low` and `high` were swapped, or a sweep/parameter substitution produced
an inconsistent pair. Worth checking any code path that programmatically
builds a `UniformDistribution` from user-supplied min/max fields (e.g. a
form) rather than assuming input order is always correct.

**Duplicate attribute name error only shows up at save time**
Because validation runs on construction, a partially-built agent type
with duplicate names in progress (e.g. two attributes both temporarily
named `"attr"` before being renamed) will fail immediately rather than
allowing an in-progress invalid state. Any UI driving this model
incrementally (e.g. an autosave-per-field wizard step) needs to either
debounce validation or only construct the final `AgentType` once names
are finalised.

**Negative `count` rejected even for a "draft" agent type**
There is no draft/partial mode that bypasses validation — `count >= 0` is
enforced unconditionally. If the wizard needs to represent "not yet
entered" for count, that should be modelled as the field being unset
upstream (e.g. in a separate draft/form-state representation), not as a
negative or sentinel value passed into `AgentType`.
