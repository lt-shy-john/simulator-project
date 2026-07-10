"""
network.py — Network topology implementation using NetworkX.

Returns graph-adjacent nodes as neighbours for each agent. The graph
is built once at simulation start via graph_builder.py and held in
memory for the duration of the simulation.

Node IDs in the graph are UUID strings matching agent IDs in the
SoAPopulation. get_neighbours(agent_id, soa) maps directly to
graph.neighbors(agent_id) — no position-based translation needed.

Self-interaction is excluded — NetworkX simple graphs do not have
self-loops by default, so an agent will never appear in its own
neighbour list unless a self-loop was explicitly added to the graph.

Cross-type interactions are included by default. Set agent_types in
config to restrict the neighbour pool to specific agent types.

The graph is undirected (nx.Graph). Directed graph support is deferred
to a later ticket.

Config shape:
    topologies:
      contact:
        mode: network
        agent_types: null       # optional, null means all types
        graph:
          type: erdos_renyi
          n: 1000
          p: 0.05
          seed: 42

      # or bring-your-own
      contact:
        mode: network
        graph:
          source: path/to/my_graph.graphml
"""

from __future__ import annotations

import networkx as nx

from runner.soa import SoAPopulation, ID_KEY
from topology.graph_builder import build_graph


class NetworkTopology:
    """Topology implementation that returns graph-adjacent agents as neighbours.

    Satisfies TopologyProtocol structurally — no inheritance needed.

    The graph is built once at construction time and reused each step.
    For dynamic rewiring (agents forming/dropping connections mid-simulation),
    see S-03b.
    """

    def __init__(
        self,
        graph: nx.Graph,
        agent_types: list[str] | None = None,
    ):
        """
        Args:
            graph: a NetworkX Graph with UUID string node labels matching
                   agent IDs in the SoAPopulation
            agent_types: if set, only neighbours of these types are returned.
                         If None, all types are included.
        """
        self.graph = graph
        self.agent_types = agent_types

    @classmethod
    def from_config(cls, config: dict, soa: SoAPopulation) -> "NetworkTopology":
        """Construct from a topology config section.

        Builds or loads the graph via graph_builder, then constructs
        the NetworkTopology instance.

        Args:
            config: the config dict for this topology, e.g.
                {
                    "mode": "network",
                    "agent_types": ["person"],
                    "graph": {
                        "type": "erdos_renyi",
                        "n": 1000,
                        "p": 0.05,
                        "seed": 42
                    }
                }
            soa: the current SoAPopulation, needed by graph_builder for
                 node relabelling and validation

        Raises:
            ValueError: if 'graph' section is missing from config
        """
        if "graph" not in config:
            raise ValueError(
                "Network topology config must contain a 'graph' section."
            )

        graph = build_graph(config["graph"], soa)

        return cls(
            graph=graph,
            agent_types=config.get("agent_types", None),
        )

    def get_neighbours(self, agent_id: str, soa: SoAPopulation) -> list[str]:
        """Return graph-adjacent agent IDs for the given agent.

        Looks up neighbours directly from the NetworkX graph using
        agent_id as the node label. Filters by agent_types if specified.

        Args:
            agent_id: the ID of the focal agent
            soa: the current SoAPopulation (used for agent_types filtering)

        Returns:
            list of neighbour agent ID strings. Empty list if the agent
            has no edges in the graph or is not in the graph.
        """
        if agent_id not in self.graph:
            return []

        # Get graph-adjacent node IDs.
        raw_neighbours = [str(n) for n in self.graph.neighbors(agent_id)]

        if self.agent_types is None:
            return raw_neighbours

        # Filter by agent_types — build a set of IDs belonging to
        # allowed types from the SoA for O(1) membership check.
        allowed_ids = self._get_allowed_ids(soa)
        return [n for n in raw_neighbours if n in allowed_ids]

    def _get_allowed_ids(self, soa: SoAPopulation) -> set[str]:
        """Build a set of agent IDs belonging to allowed agent_types."""
        allowed: set[str] = set()
        for type_name, arrays in soa.items():
            if self.agent_types is not None and type_name not in self.agent_types:
                continue
            allowed.update(str(id_) for id_ in arrays[ID_KEY])
        return allowed