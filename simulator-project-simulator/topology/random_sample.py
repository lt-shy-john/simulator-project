"""
random_sample.py — Random sample topology implementation.

Returns a random subset of the population as neighbours for each agent.
Supports two sampling modes:
  - Fixed (k): always return exactly k neighbours
  - Proportional: return k% of the eligible population

Sampling is with replacement, so duplicates are possible when k is large
relative to population size. If k exceeds the eligible pool size in fixed
mode, all eligible agents are returned (capped, no error raised).

Self-interaction is excluded — agent A will never appear in its own
neighbour list. This is not configurable in the current implementation;
see S-03b for future extensions.

Cross-type interactions are included by default. Set agent_types in config
to restrict the neighbour pool to specific agent types.

Each topology instance can have its own random seed for reproducibility.
Global seeding (S-11) can override this later — the seed here is
topology-local only.

Config shape:
    topologies:
      disease_spread:
        mode: random_sample
        k: 5                        # fixed sample size
        seed: 42                    # optional
        agent_types: null           # null means all types

      social_influence:
        mode: random_sample
        proportion: 0.1             # 10% of eligible population
        seed: 123
        agent_types:
          - person
"""

from __future__ import annotations

import math
import numpy as np

from runner.soa import SoAPopulation, ID_KEY


class RandomSampleTopology:
    """Topology implementation that returns a random subset of agents
    as neighbours.

    Satisfies TopologyProtocol structurally — no inheritance needed.
    """

    def __init__(
        self,
        k: int | None = None,
        proportion: float | None = None,
        seed: int | None = None,
        agent_types: list[str] | None = None,
    ):
        """
        Args:
            k: fixed number of neighbours to sample. Mutually exclusive
                with proportion.
            proportion: fraction of eligible population to sample (0.0–1.0).
                Mutually exclusive with k.
            seed: random seed for this topology instance. Optional.
            agent_types: if set, only agents of these types are eligible
                as neighbours. If None, all types are included.

        Raises:
            ValueError: if neither or both of k and proportion are set,
                or if proportion is outside (0.0, 1.0].
        """
        if k is None and proportion is None:
            raise ValueError("RandomSampleTopology requires either 'k' or 'proportion'.")
        if k is not None and proportion is not None:
            raise ValueError("RandomSampleTopology requires either 'k' or 'proportion', not both.")
        if proportion is not None and not (0.0 < proportion <= 1.0):
            raise ValueError(f"proportion must be in (0.0, 1.0], got {proportion}.")
        if k is not None and k < 1:
            raise ValueError(f"k must be >= 1, got {k}.")

        self.k = k
        self.proportion = proportion
        self.agent_types = agent_types
        self.rng = np.random.default_rng(seed)

    @classmethod
    def from_config(cls, config: dict) -> "RandomSampleTopology":
        """Construct from a topology config section.

        Args:
            config: the config dict for this topology, e.g.
                {
                    "mode": "random_sample",
                    "k": 5,
                    "seed": 42,
                    "agent_types": ["person"]
                }
        """
        return cls(
            k=config.get("k", None),
            proportion=config.get("proportion", None),
            seed=config.get("seed", None),
            agent_types=config.get("agent_types", None),
        )

    def _get_eligible_pool(self, agent_id: str, soa: SoAPopulation) -> list[str]:
        """Build the eligible neighbour pool, excluding self and
        filtering by agent_types if specified."""
        pool: list[str] = []

        for type_name, arrays in soa.items():
            if self.agent_types is not None and type_name not in self.agent_types:
                continue
            for id_ in arrays[ID_KEY]:
                id_str = str(id_)
                if id_str != agent_id:  # always exclude self
                    pool.append(id_str)

        return pool

    def _sample_size(self, pool_size: int) -> int:
        """Determine how many neighbours to sample given the pool size."""
        if self.k is not None:
            # Fixed mode — cap at pool size to avoid errors
            return min(self.k, pool_size)
        else:
            # Proportional mode — at least 1 neighbour
            return max(1, math.ceil(self.proportion * pool_size))

    def get_neighbours(self, agent_id: str, soa: SoAPopulation) -> list[str]:
        """Return a random sample of agent IDs from the eligible pool.

        Sampling is with replacement. Self is always excluded.

        Args:
            agent_id: the ID of the focal agent
            soa: the current SoAPopulation

        Returns:
            list of neighbour agent ID strings, length determined by
            k or proportion. Empty list if no eligible neighbours exist.
        """
        pool = self._get_eligible_pool(agent_id, soa)

        if not pool:
            return []

        sample_size = self._sample_size(len(pool))
        indices = self.rng.integers(0, len(pool), size=sample_size)
        return [pool[i] for i in indices]