"""
Structure of Arrays (SoA) conversion module.

Scope:
  - to_soa: converts list[AgentState] → SoAPopulation (per agent type)
  - from_soa: converts SoAPopulation → list[AgentState] (two-way)
  - add_agent: appends a new agent to an existing SoAPopulation
  - remove_agent: removes an agent by ID from an existing SoAPopulation
  - SoAPopulation is a plain dict for performance — no Pydantic overhead

Structure:
  SoAPopulation is typed as dict[str, dict[str, np.ndarray]] where:
    - outer key: agent_type_name (e.g. "predator", "prey")
    - inner key: attribute name, plus a reserved "__ids__" key for agent IDs
    - value: np.ndarray of length N (one entry per agent of that type)

  Example:
    {
      "predator": {
        "__ids__":  np.array(["uuid-1", "uuid-2"]),
        "energy":   np.array([95.2, 87.1]),
        "infected": np.array([False, True]),
      },
      "prey": {
        "__ids__":  np.array(["uuid-3"]),
        "energy":   np.array([72.4]),
      }
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Adjust to relative imports when placed inside your project.
from runner.state import AgentState


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

# SoAPopulation: { agent_type_name: { attr_name: np.ndarray } }
# "__ids__" is a reserved key in the inner dict holding agent UUIDs.
SoAPopulation = dict[str, dict[str, np.ndarray]]

ID_KEY = "__ids__"


# ---------------------------------------------------------------------------
# Conversion: list[AgentState] → SoAPopulation
# ---------------------------------------------------------------------------

def to_soa(agents: list[AgentState]) -> SoAPopulation:
    """Convert a flat list of AgentState instances into a SoAPopulation.

    Agents are grouped by agent_type_name. Within each group, one NumPy
    array is produced per attribute, plus a reserved "__ids__" array
    holding agent UUIDs for backtracking.

    O(N) in the number of agents.
    """
    # Group agents by type first.
    grouped: dict[str, list[AgentState]] = {}
    for agent in agents:
        grouped.setdefault(agent.agent_type_name, []).append(agent)

    soa: SoAPopulation = {}
    for type_name, type_agents in grouped.items():
        # ID array — always present, reserved key.
        ids = np.array([a.agent_id for a in type_agents])

        # Attribute arrays — one per key in state dict.
        # Infer dtype from the values themselves; let NumPy decide.
        attr_arrays: dict[str, np.ndarray] = {ID_KEY: ids}
        if type_agents:
            for attr_name in type_agents[0].state.keys():
                attr_arrays[attr_name] = np.array(
                    [a.state[attr_name] for a in type_agents]
                )

        soa[type_name] = attr_arrays

    return soa


# ---------------------------------------------------------------------------
# Conversion: SoAPopulation → list[AgentState]
# ---------------------------------------------------------------------------

def from_soa(soa: SoAPopulation) -> list[AgentState]:
    """Convert a SoAPopulation back into a flat list of AgentState instances.

    Reconstructs each agent's state dict by slicing the i-th value from
    each attribute array. Agent IDs are restored from the "__ids__" array.

    O(N) in the number of agents.
    """
    agents: list[AgentState] = []

    for type_name, arrays in soa.items():
        ids = arrays[ID_KEY]
        attr_names = [k for k in arrays.keys() if k != ID_KEY]
        count = len(ids)

        for i in range(count):
            state = {
                attr: (
                    arrays[attr][i].item()
                    if isinstance(arrays[attr][i], np.generic)
                    else arrays[attr][i]
                )
                for attr in attr_names
            }
            agents.append(AgentState(
                agent_id=str(ids[i]),
                agent_type_name=type_name,
                state=state,
            ))

    return agents


# ---------------------------------------------------------------------------
# Agent addition
# ---------------------------------------------------------------------------

def add_agent(soa: SoAPopulation, agent: AgentState) -> SoAPopulation:
    """Append a new agent to an existing SoAPopulation.

    If the agent's type already exists in the SoA, appends to each
    attribute array. If it's a new type, creates a new entry.

    O(N) due to np.append rebuilding the arrays — acceptable for
    infrequent additions during a simulation run. If additions are
    frequent and N is large, consider batching additions and applying
    them once per step rather than one at a time.
    """
    type_name = agent.agent_type_name

    if type_name not in soa:
        # New type — create fresh arrays from this agent's state.
        soa[type_name] = {
            ID_KEY: np.array([agent.agent_id]),
            **{
                attr: np.array([value])
                for attr, value in agent.state.items()
            }
        }
    else:
        # Existing type — append to each array.
        arrays = soa[type_name]
        arrays[ID_KEY] = np.append(arrays[ID_KEY], agent.agent_id)
        for attr, value in agent.state.items():
            if attr in arrays:
                arrays[attr] = np.append(arrays[attr], value)
            else:
                # New attribute not previously in this type's arrays.
                # Pad existing agents with None, append new value.
                arrays[attr] = np.append(
                    np.full(len(arrays[ID_KEY]) - 1, None),
                    value
                )

    return soa


# ---------------------------------------------------------------------------
# Agent removal
# ---------------------------------------------------------------------------

def remove_agent(soa: SoAPopulation, agent_id: str) -> SoAPopulation:
    """Remove an agent by ID from a SoAPopulation.

    Finds the agent's type and index via the "__ids__" array, then
    masks that index out of all attribute arrays for that type.

    Raises KeyError if the agent_id is not found in any type.

    O(N) due to array rebuilding after masking.
    """
    for type_name, arrays in soa.items():
        ids = arrays[ID_KEY]
        indices = np.where(ids == agent_id)[0]

        if len(indices) == 0:
            continue

        # Found — mask out this index from all arrays.
        idx = indices[0]
        mask = np.ones(len(ids), dtype=bool)
        mask[idx] = False

        soa[type_name] = {
            key: arr[mask]
            for key, arr in arrays.items()
        }

        # Clean up empty type entry if no agents remain.
        if len(soa[type_name][ID_KEY]) == 0:
            del soa[type_name]

        return soa

    raise KeyError(
        f"agent_id '{agent_id}' not found in SoAPopulation. "
        f"Known types: {list(soa.keys())}"
    )