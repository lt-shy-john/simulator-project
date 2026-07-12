"""
graph_builder.py — NetworkX graph construction and loading.

Scope:
  - Build graphs from config (erdos_renyi, barabasi_albert, watts_strogatz)
  - Load graphs from file (GraphML, GML, edgelist, adjacency list)
  - Validate that graph node IDs match SoA agent IDs
  - All graphs are undirected (networkx.Graph)

Node labelling:
  All graphs use UUID strings as node labels, matching agent IDs in the
  SoAPopulation. Bring-your-own graphs must use UUID node labels — integer
  node IDs will fail validation. This ensures get_neighbours(agent_id)
  maps directly to graph.neighbors(agent_id) without any position-based
  translation, which would break when agents are added or removed.

Supported graph types (generated):
  - erdos_renyi: random graph with n nodes and edge probability p
  - barabasi_albert: scale-free graph with n nodes, m edges per new node
  - watts_strogatz: small-world graph with n nodes, k nearest neighbours,
    rewiring probability p

Supported file formats (bring-your-own):
  - .graphml
  - .gml
  - .edgelist
  - .adjlist

Config shape (generated):
    graph:
      type: erdos_renyi
      n: 1000
      p: 0.05
      seed: 42        # optional

    graph:
      type: barabasi_albert
      n: 1000
      m: 3
      seed: 42

    graph:
      type: watts_strogatz
      n: 1000
      k: 4
      p: 0.1
      seed: 42

Config shape (bring-your-own):
    graph:
      source: path/to/my_graph.graphml
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from runner.soa import SoAPopulation, ID_KEY


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------

_FILE_READERS = {
    ".graphml": nx.read_graphml,
    ".gml":     nx.read_gml,
    ".edgelist": nx.read_edgelist,
    ".adjlist":  nx.read_adjlist,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_graph(config: dict, soa: SoAPopulation) -> nx.Graph:
    """Build or load a NetworkX graph from config.

    If config contains 'source', loads from file.
    If config contains 'type', generates from parameters.

    In both cases, validates that graph node IDs match SoA agent IDs.

    Args:
        config: the 'graph' section of the topology config
        soa: the current SoAPopulation, used for agent ID validation
             and node relabelling for generated graphs

    Returns:
        nx.Graph with UUID string node labels matching SoA agent IDs

    Raises:
        ValueError: unknown graph type, missing required params,
                    or node IDs don't match SoA agent IDs
        FileNotFoundError: source file does not exist
        KeyError: unsupported file format
    """
    if "source" in config:
        graph = _load_graph(config["source"])
    elif "type" in config:
        graph = _generate_graph(config, soa)
    else:
        raise ValueError("Graph config must contain either 'source' or 'type'.")

    _validate_graph(graph, soa)
    return graph


# ---------------------------------------------------------------------------
# Graph generation
# ---------------------------------------------------------------------------

def _generate_graph(config: dict, soa: SoAPopulation) -> nx.Graph:
    """Generate a NetworkX graph from config parameters.

    Nodes are labelled with UUID strings from the SoA agent IDs.
    The graph is generated with integer nodes first (NetworkX default)
    then relabelled to match agent IDs.

    Args:
        config: graph config section containing 'type' and parameters
        soa: SoAPopulation providing agent IDs for node relabelling

    Returns:
        nx.Graph with UUID string node labels
    """
    graph_type = config.get("type")
    seed = config.get("seed", None)

    # Collect all agent IDs from SoA in order — used for node relabelling.
    agent_ids = _collect_agent_ids(soa)

    if graph_type == "erdos_renyi":
        n = _require(config, "n", graph_type)
        p = _require(config, "p", graph_type)
        _check_node_count(n, agent_ids, graph_type)
        graph = nx.erdos_renyi_graph(n=n, p=p, seed=seed)

    elif graph_type == "barabasi_albert":
        n = _require(config, "n", graph_type)
        m = _require(config, "m", graph_type)
        _check_node_count(n, agent_ids, graph_type)
        graph = nx.barabasi_albert_graph(n=n, m=m, seed=seed)

    elif graph_type == "watts_strogatz":
        n = _require(config, "n", graph_type)
        k = _require(config, "k", graph_type)
        p = _require(config, "p", graph_type)
        _check_node_count(n, agent_ids, graph_type)
        graph = nx.watts_strogatz_graph(n=n, k=k, p=p, seed=seed)

    else:
        raise ValueError(
            f"Unknown graph type '{graph_type}'. "
            f"Expected one of: erdos_renyi, barabasi_albert, watts_strogatz."
        )

    # Relabel integer nodes (0, 1, 2...) to UUID strings.
    mapping = {i: agent_ids[i] for i in range(len(agent_ids))}
    return nx.relabel_nodes(graph, mapping)


# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------

def _load_graph(source: str) -> nx.Graph:
    """Load a graph from a file.

    Node IDs in the file must be UUID strings matching SoA agent IDs.
    Integer node IDs will fail validation downstream.

    Args:
        source: path to the graph file

    Returns:
        nx.Graph loaded from file

    Raises:
        FileNotFoundError: file does not exist
        ValueError: unsupported file format
    """
    path = Path(source)

    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: '{source}'")

    suffix = path.suffix.lower()
    if suffix not in _FILE_READERS:
        raise ValueError(
            f"Unsupported graph file format '{suffix}'. "
            f"Expected one of: {', '.join(_FILE_READERS.keys())}"
        )

    return _FILE_READERS[suffix](source)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_graph(graph: nx.Graph, soa: SoAPopulation) -> None:
    """Validate that graph node IDs match SoA agent IDs exactly.

    Raises ValueError with a descriptive message if:
      - Graph nodes are not a subset of SoA agent IDs
      - SoA agent IDs are not a subset of graph nodes
      (i.e. the sets must be equal)

    Args:
        graph: the NetworkX graph to validate
        soa: the current SoAPopulation

    Raises:
        ValueError: if node IDs don't match SoA agent IDs
    """
    graph_nodes = set(str(n) for n in graph.nodes())
    agent_ids = set(_collect_agent_ids(soa))

    in_graph_not_soa = graph_nodes - agent_ids
    in_soa_not_graph = agent_ids - graph_nodes

    errors = []
    if in_graph_not_soa:
        errors.append(
            f"Graph contains {len(in_graph_not_soa)} node(s) not in SoA: "
            f"{sorted(in_graph_not_soa)[:5]}{'...' if len(in_graph_not_soa) > 5 else ''}"
        )
    if in_soa_not_graph:
        errors.append(
            f"SoA contains {len(in_soa_not_graph)} agent(s) not in graph: "
            f"{sorted(in_soa_not_graph)[:5]}{'...' if len(in_soa_not_graph) > 5 else ''}"
        )
    if errors:
        raise ValueError(
            "Graph node IDs do not match SoA agent IDs:\n" + "\n".join(errors)
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_agent_ids(soa: SoAPopulation) -> list[str]:
    """Collect all agent IDs from SoA in type-then-position order."""
    ids = []
    for arrays in soa.values():
        ids.extend(str(id_) for id_ in arrays[ID_KEY])
    return ids


def _require(config: dict, key: str, graph_type: str) -> any:
    """Get a required config parameter, raising a clear error if missing."""
    if key not in config:
        raise ValueError(
            f"Graph type '{graph_type}' requires '{key}' in config."
        )
    return config[key]


def _check_node_count(n: int, agent_ids: list[str], graph_type: str) -> None:
    """Validate that n matches the number of agents in the SoA."""
    if n != len(agent_ids):
        raise ValueError(
            f"Graph type '{graph_type}': n={n} does not match "
            f"total agent count={len(agent_ids)} in SoA. "
            f"These must be equal for node relabelling to work."
        )