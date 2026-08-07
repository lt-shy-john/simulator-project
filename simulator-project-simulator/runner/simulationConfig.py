from typing import Any
from pydantic import BaseModel, Field, model_validator

from agents.agents import AgentType
from stopping.engine import StoppingConfig

class SimulationConfig(BaseModel):
    seed: int | None = None

    agent_types: list[AgentType]

    # Literal per-agent overrides — e.g. from CSV import. Keyed by agent
    # type name. Agents here take precedence over generated ones, up to
    # each type's `count`; any shortfall is filled by normal generation.
    initial_population: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)

    topologies: dict[str, dict]
    behaviours: dict[str, list[dict]]
    scheduler: dict
    stopping: StoppingConfig

    @model_validator(mode="after")
    def _check_agent_type_names_unique(self) -> "SimulationConfig":
        names = [a.name for a in self.agent_types]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate agent type names: {sorted(dupes)}")
        return self