import uuid
from typing import Any
import numpy as np
from pydantic import BaseModel, Field, model_validator

from agents.agents import AgentType
from agents.attributeDefinition import AttributeDefinition
from agents.distributions import (
    FixedDistribution,
    UniformDistribution,
    NormalDistribution,
    CategoricalDistribution,
    BinomialDistribution,
    PoissonDistribution,
)
from agents.models import AttributeType, PopulationMethod


# ---------------------------------------------------------------------------
# Distribution sampling
# ---------------------------------------------------------------------------

def _sample_distribution(attr: AttributeDefinition, count: int) -> np.ndarray:
    """Sample `count` values from the distribution defined on `attr`.

    Returns a NumPy array of length `count`. The dtype is inferred from the
    attribute type rather than the distribution, since e.g. a normal
    distribution over an int attribute should produce rounded integers.
    """
    dist = attr.distribution

    if isinstance(dist, FixedDistribution):
        # All agents get the same value — broadcast a constant array.
        return np.full(count, dist.value)

    if isinstance(dist, UniformDistribution):
        if attr.type == AttributeType.INT:
            # randint is exclusive of high, so +1 to make it inclusive.
            return np.random.randint(int(dist.low), int(dist.high) + 1, size=count)
        return np.random.uniform(dist.low, dist.high, size=count)

    if isinstance(dist, NormalDistribution):
        samples = np.random.normal(dist.mean, dist.stddev, size=count)
        if attr.type == AttributeType.INT:
            return np.round(samples).astype(int)
        return samples

    if isinstance(dist, CategoricalDistribution):
        categories = list(dist.weights.keys())
        total = sum(dist.weights.values())
        probabilities = [w / total for w in dist.weights.values()]
        return np.random.choice(categories, size=count, p=probabilities)

    if isinstance(dist, BinomialDistribution):
        return np.random.binomial(dist.n, dist.p, size=count)

    if isinstance(dist, PoissonDistribution):
        return np.random.poisson(dist.lam, size=count)

    raise ValueError(
        f"attribute '{attr.name}': unsupported distribution type '{type(dist).__name__}'"
    )


# ---------------------------------------------------------------------------
# AgentState — runtime representation of a single agent
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """Runtime state for a single agent instance.

    Intentionally separate from AgentType (the authoring/config layer).
    AgentType is the blueprint; AgentState is the live instance produced
    from that blueprint at simulation start.

    state dict keys are attribute names from the AgentType's AttributeDefinition
    list. Accessing an undefined key raises a descriptive KeyError.
    """

    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_type_name: str
    state: dict[str, Any] = Field(default_factory=dict)

    # Mutation tracking — infrastructure for quota mode.
    # The rules that decide when to increment these live in Behaviour (S-05).
    mutation_count: int = 0

    model_config = {"arbitrary_types_allowed": True}

    def get(self, attr_name: str) -> Any:
        """Read an attribute from state. Raises KeyError if undefined."""
        if attr_name not in self.state:
            raise KeyError(
                f"agent '{self.agent_id}' (type '{self.agent_type_name}') "
                f"has no attribute '{attr_name}'. "
                f"Available attributes: {sorted(self.state.keys())}"
            )
        return self.state[attr_name]

    def set(self, attr_name: str, value: Any) -> None:
        """Write an attribute to state. Raises KeyError if undefined.

        Only allows updating existing attributes — new keys cannot be added
        at runtime, since they weren't part of the original AgentType schema.
        """
        if attr_name not in self.state:
            raise KeyError(
                f"agent '{self.agent_id}' (type '{self.agent_type_name}') "
                f"has no attribute '{attr_name}'. "
                f"Available attributes: {sorted(self.state.keys())}"
            )
        self.state[attr_name] = value
        self.mutation_count += 1

    def snapshot(self) -> "AgentState":
        """Return a deep copy of this agent's state for snapshot-based updates.

        The simulation engine should:
          1. Call snapshot() on all agents at the start of each step.
          2. Apply all state updates to the snapshots.
          3. Swap snapshots back as the live state at the end of the step.

        This avoids order-dependency bugs where agent A's update at t affects
        agent B's decision at t within the same step.
        """
        return self.model_copy(deep=True)


# ---------------------------------------------------------------------------
# Population initialisation
# ---------------------------------------------------------------------------

def initialise_population(agent_type: AgentType) -> list[AgentState]:
    """Initialise a population of AgentState instances from an AgentType blueprint.

    Samples attribute values using NumPy (one array per attribute, not per
    agent) then slices per-agent values from the resulting arrays.

    Only processes attributes with a defined population_method and distribution.
    Attributes without a distribution (e.g. schema-only heterogeneous agents
    awaiting bulk import) are initialised to None and flagged with a warning.
    """
    count = agent_type.count

    # Sample all attribute values upfront as arrays — one array per attribute.
    # This is the NumPy-first approach: sample in bulk, then distribute to agents.
    attribute_arrays: dict[str, np.ndarray | list] = {}

    for attr in agent_type.attributes:
        if attr.distribution is not None:
            attribute_arrays[attr.name] = _sample_distribution(attr, count)
        else:
            # No distribution defined — initialise to None for now.
            # This covers schema-only heterogeneous attributes awaiting bulk import.
            print(
                f"Warning: attribute '{attr.name}' on agent type '{agent_type.name}' "
                f"has no distribution defined. Initialising to None."
            )
            attribute_arrays[attr.name] = [None] * count

    # Build one AgentState per agent by slicing the i-th value from each array.
    agents: list[AgentState] = []
    for i in range(count):
        state = {
            attr_name: (
                values[i].item()  # .item() converts numpy scalar to Python native type
                if isinstance(values[i], np.generic)
                else values[i]
            )
            for attr_name, values in attribute_arrays.items()
        }
        agents.append(AgentState(agent_type_name=agent_type.name, state=state))

    return agents


# ---------------------------------------------------------------------------
# Snapshot swap — simulation step helper
# ---------------------------------------------------------------------------

def apply_snapshot_updates(
    current: list[AgentState],
    updates: list[AgentState]
) -> list[AgentState]:
    """Swap snapshot updates back as the live population state.

    Usage in the simulation loop:
        snapshots = [agent.snapshot() for agent in population]
        # ... behaviour rules write updates to snapshots ...
        population = apply_snapshot_updates(population, snapshots)

    Preserves agent_id ordering and carries forward mutation counts.
    """
    if len(current) != len(updates):
        raise ValueError(
            f"population size mismatch: current={len(current)}, updates={len(updates)}"
        )
    for agent, update in zip(current, updates):
        agent.state = update.state
        agent.mutation_count = update.mutation_count
    return current