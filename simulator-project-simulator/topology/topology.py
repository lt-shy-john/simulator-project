"""
topology.py — Protocol definition and factory for multiplex topologies.

Scope:
  - TopologyProtocol: structural interface all topology implementations satisfy
  - build_topologies: factory that reads config and returns dict of named topologies

Not in scope:
  - Individual topology implementations (all_pairs.py, random_sample.py, network.py)
  - Graph construction (graph_builder.py)
  - Dynamic rewiring (S-03b)

Multiplex topology:
  Multiple named topologies can be active simultaneously. For example,
  a disease model might have a contact network for infection spread and
  a random sample layer for opinion influence:

    topologies:
      contact:
        mode: network
        graph:
          type: erdos_renyi
          n: 1000
          p: 0.05
      social:
        mode: random_sample
        k: 5

  build_topologies returns:
    {
      "contact": NetworkTopology(...),
      "social": RandomSampleTopology(k=5),
    }

  Behaviour modules reference topologies by name:
    infection_neighbours = topologies["contact"].get_neighbours(agent_id, soa)
    opinion_neighbours = topologies["social"].get_neighbours(agent_id, soa)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from runner.soa import SoAPopulation


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class TopologyProtocol(Protocol):
    """Structural interface for all topology implementations.

    Any class implementing get_neighbours and from_config satisfies
    this Protocol — no inheritance required.

    @runtime_checkable allows isinstance() checks at runtime, useful
    for factory validation and testing.
    """

    def get_neighbours(self, agent_id: str, soa: SoAPopulation) -> list[str]:
        """Return list of agent ID strings that are neighbours of agent_id.

        Called once per agent per simulation step. Behaviour modules
        consume this list without knowing which topology is active.

        Self-interaction is excluded by default across all implementations.

        Args:
            agent_id: the ID of the focal agent
            soa: the current SoAPopulation

        Returns:
            list of neighbour agent ID strings
        """
        ...

    @classmethod
    def from_config(cls, config: dict, soa: SoAPopulation) -> "TopologyProtocol":
        """Construct this topology from a config dict section.

        Each implementation parses its own relevant keys from config.
        soa is required by NetworkTopology for graph node relabelling
        and validation; other implementations may ignore it.

        Args:
            config: the config section for this topology
            soa: the current SoAPopulation
        """
        ...


# ---------------------------------------------------------------------------
# Shared validation
# ---------------------------------------------------------------------------

def validate_agent_types(agent_types: list[str] | None, soa: SoAPopulation) -> None:
    """Validate that every type name in agent_types exists in the SoAPopulation.

    Shared across all_pairs, random_sample, and network topology implementations
    to keep validation behaviour consistent. Raises loudly rather than silently
    filtering to an empty neighbour list, which would otherwise be very hard
    to debug (e.g. a typo'd agent type name silently produces an empty
    simulation with no error).

    Args:
        agent_types: list of agent type names to validate, or None (no-op)
        soa: the current SoAPopulation, used as the source of truth for
             which agent types actually exist

    Raises:
        ValueError: if any name in agent_types is not a known agent type in soa
    """
    if agent_types is None:
        return

    known_types = set(soa.keys())
    unknown = [t for t in agent_types if t not in known_types]

    if unknown:
        raise ValueError(
            f"agent_types contains unknown type(s): {unknown}. "
            f"Known agent types in population: {sorted(known_types)}"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_topologies(config: dict, soa: SoAPopulation) -> dict[str, TopologyProtocol]:
    """Factory — reads the 'topologies' section of the simulation config
    and returns a dict of named topology instances.

    Args:
        config: the full simulation config dict containing a 'topologies' section
        soa: the current SoAPopulation, passed through to topology constructors

    Returns:
        dict mapping topology name to topology instance, e.g.
        {
            "contact": NetworkTopology(...),
            "social": RandomSampleTopology(k=5),
        }

    Raises:
        ValueError: if 'topologies' section is missing or empty
    """
    topologies_config = config.get("topologies", {})
    if not topologies_config:
        raise ValueError(
            "Config must contain a 'topologies' section with at least one topology."
        )

    return {
        name: _build_single_topology(name, topology_config, soa)
        for name, topology_config in topologies_config.items()
    }


def _build_single_topology(
    name: str,
    config: dict,
    soa: SoAPopulation,
) -> TopologyProtocol:
    """Internal factory — constructs a single topology from its config section.

    Lazy imports avoid circular dependencies between topology modules.

    Args:
        name: the topology name (used in error messages)
        config: the config section for this topology
        soa: the current SoAPopulation

    Raises:
        ValueError: if mode is unknown or missing
    """
    mode = config.get("mode")

    if mode == "all_pairs":
        from topology.all_pairs import AllPairsTopology
        return AllPairsTopology.from_config(config, soa)

    elif mode == "random_sample":
        from topology.random_sample import RandomSampleTopology
        return RandomSampleTopology.from_config(config, soa)

    elif mode == "network":
        from topology.network import NetworkTopology
        return NetworkTopology.from_config(config, soa)

    else:
        raise ValueError(
            f"Topology '{name}' has unknown mode '{mode}'. "
            f"Expected one of: all_pairs, random_sample, network."
        )