from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, model_validator

from agents.agents import AgentType
from stopping.engine import StoppingConfig

"""
simulationConfig.py — SimulationConfig and its Pydantic sub-models.

topologies, behaviours, and scheduler are real Pydantic sub-models (not
plain dicts) — validated the moment SimulationConfig.model_validate()
runs, same as agent_types and stopping already were.

Field shapes deliberately mirror what the existing S-03/S-05/S-06
factories (build_topologies, compile_behaviours, compile_scheduling)
already expect when the models are .model_dump()'d — no changes needed
to those factories. NetworkTopologyConfig.graph is kept as a plain dict:
graph_builder.build_graph() already validates it (type-specific required
fields, node-count checks) with descriptive ValueErrors, so re-modelling
that surface in Pydantic would duplicate validation logic that already
exists and risk the two drifting apart.
"""

# ---------------------------------------------------------------------------
# Topology sub-models — discriminated union on 'mode'
# ---------------------------------------------------------------------------

class AllPairsTopologyConfig(BaseModel):
    mode: Literal["all_pairs"]
    agent_types: list[str] | None = None
    allow_self_interaction: bool = False


class RandomSampleTopologyConfig(BaseModel):
    mode: Literal["random_sample"]
    k: int | None = None
    proportion: float | None = None
    seed: int | None = None
    agent_types: list[str] | None = None

    @model_validator(mode="after")
    def _check_k_xor_proportion(self) -> "RandomSampleTopologyConfig":
        if (self.k is None) == (self.proportion is None):
            raise ValueError(
                "random_sample topology requires exactly one of 'k' or "
                "'proportion', not both or neither."
            )
        if self.proportion is not None and not (0.0 < self.proportion <= 1.0):
            raise ValueError(f"proportion must be in (0.0, 1.0], got {self.proportion}.")
        if self.k is not None and self.k < 1:
            raise ValueError(f"k must be >= 1, got {self.k}.")
        return self


class NetworkTopologyConfig(BaseModel):
    mode: Literal["network"]
    agent_types: list[str] | None = None
    # Validated lazily by graph_builder.build_graph — see module docstring.
    graph: dict[str, Any]


TopologyConfig = Annotated[
    Union[AllPairsTopologyConfig, RandomSampleTopologyConfig, NetworkTopologyConfig],
    Field(discriminator="mode"),
]


# ---------------------------------------------------------------------------
# Behaviour sub-models — union on presence of 'module' vs 'expression'
# ---------------------------------------------------------------------------

class ModuleBehaviourEntry(BaseModel):
    module: str
    params: dict[str, Any] = Field(default_factory=dict)
    topology_name: str | None = None
    write_mode: Literal["deferred", "immediate"] = "deferred"


class ExpressionBehaviourEntry(BaseModel):
    expression: str
    topology_name: str | None = None


# No shared discriminator field (module vs expression are different key
# names), so this relies on Pydantic v2's default "smart" union matching —
# each entry has a distinct required field, so exactly one member validates.
BehaviourEntry = Union[ModuleBehaviourEntry, ExpressionBehaviourEntry]


# ---------------------------------------------------------------------------
# Scheduler sub-models
# ---------------------------------------------------------------------------

class QuotaConfigSchema(BaseModel):
    mode: Literal["step_random_subset", "lifetime_budget"]
    limit: int
    scope: str | None = None

    @model_validator(mode="after")
    def _check_limit(self) -> "QuotaConfigSchema":
        if self.limit < 1:
            raise ValueError(f"quota.limit must be a positive integer, got {self.limit}.")
        return self


class SchedulerConfigSchema(BaseModel):
    order: Literal["all_at_once", "random", "priority"]
    read_mode: Literal["frozen", "live"]
    priority_attribute: str | None = None
    quota: QuotaConfigSchema | None = None

    @model_validator(mode="after")
    def _check_priority_attribute_required(self) -> "SchedulerConfigSchema":
        if self.order == "priority" and not self.priority_attribute:
            raise ValueError(
                "scheduler.order is 'priority' but no priority_attribute was given."
            )
        return self


# ---------------------------------------------------------------------------
# Top-level SimulationConfig
# ---------------------------------------------------------------------------

class SimulationConfig(BaseModel):
    seed: int | None = None

    agent_types: list[AgentType]

    # Literal per-agent overrides — e.g. from CSV import. Keyed by agent
    # type name. Agents here take precedence over generated ones, up to
    # each type's `count`; any shortfall is filled by normal generation.
    initial_population: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)

    topologies: dict[str, TopologyConfig]
    behaviours: dict[str, list[BehaviourEntry]]
    scheduler: SchedulerConfigSchema
    stopping: StoppingConfig

    @model_validator(mode="after")
    def _check_agent_type_names_unique(self) -> "SimulationConfig":
        names = [a.name for a in self.agent_types]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate agent type names: {sorted(dupes)}")
        return self