"""
all_pairs.py — All-pairs topology implementation.

Returns the full directed neighbour set for each agent — every other agent
in the population is a neighbour. This produces N-1 neighbours per agent
(N² - N total pairs across the population).

Self-interaction is excluded by default. This means agent A will never
appear in its own neighbour list. This is not configurable in the current
implementation — enabling self-interaction is an unusual case and deferred
to a later ticket if needed.

Cross-type interactions are included by default — get_neighbours for a
predator returns both predator and prey IDs. To restrict to specific
types, set agent_types in the topology config.

Unordered pairs optimisation (N(N-1)/2 instead of N²) is deferred to a
later optimisation ticket — only relevant for symmetric interactions like
physical collision where (A,B) and (B,A) are the same interaction.

Config shape:
    topologies:
      contact:
        mode: all_pairs
        agent_types: null           # optional, null means all types
        # or
        agent_types:
          - predator
          - prey
"""

from __future__ import annotations

from runner.soa import SoAPopulation, ID_KEY
from topology.topology import validate_agent_types


class AllPairsTopology:
    """Topology implementation that returns all other agents as neighbours.

    Satisfies TopologyProtocol structurally — no inheritance needed.
    """

    def __init__(
        self,
        allow_self_interaction: bool = False,
        agent_types: list[str] | None = None,
    ):
        """
        Args:
            allow_self_interaction: if True, agent appears in its own
                neighbour list. Default False.
            agent_types: if set, only agents of these types are returned
                as neighbours. If None, all types are included.
        """
        self.allow_self_interaction = allow_self_interaction
        self.agent_types = agent_types

    @classmethod
    def from_config(cls, config: dict, soa: SoAPopulation) -> "AllPairsTopology":
        """Construct from a topology config section.

        Args:
            config: the config dict for this topology, e.g.
                {
                    "mode": "all_pairs",
                    "agent_types": ["predator", "prey"]
                }
            soa: the current SoAPopulation, used to validate agent_types
                 refers to real agent types present in the population

        Raises:
            ValueError: if agent_types contains a type not present in soa
        """
        agent_types = config.get("agent_types", None)
        validate_agent_types(agent_types, soa)

        return cls(
            allow_self_interaction=config.get("allow_self_interaction", False),
            agent_types=agent_types,
        )

    def get_neighbours(self, agent_id: str, soa: SoAPopulation) -> list[str]:
        """Return all agent IDs in the population except self (by default).

        Iterates over all agent types in the SoA, collecting IDs from
        each type's __ids__ array. Filters by agent_types if specified.

        Args:
            agent_id: the ID of the focal agent
            soa: the current SoAPopulation

        Returns:
            list of neighbour agent ID strings
        """
        neighbours: list[str] = []

        for type_name, arrays in soa.items():
            # Filter by agent_types if specified
            if self.agent_types is not None and type_name not in self.agent_types:
                continue

            for id_ in arrays[ID_KEY]:
                id_str = str(id_)
                # Exclude self unless allow_self_interaction is True
                if not self.allow_self_interaction and id_str == agent_id:
                    continue
                neighbours.append(id_str)

        return neighbours