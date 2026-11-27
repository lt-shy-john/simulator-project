import pytest
import numpy as np
import copy
from typing import Any

from behaviour.expressions import evaluate_expression, run_rule_steps, _safe_eval, _uses_neighbours
from behaviour.expression_steps import build_rule_steps, calls_neighbour_helper
from runner.simulation import Simulation
from runner.state import AgentState


# helper

class StubAgent:
    """Minimal stand-in for AgentState (swap for your real fixture)."""

    def __init__(self, state: dict[str, Any], agent_id: int = 1) -> None:
        """Create a stub agent with the given state."""
        self.state = dict(state)
        self.agent_id = agent_id

    def get(self, key: str) -> Any:
        """Return one state value."""
        return self.state[key]

    def set(self, key: str, value: Any) -> None:
        """Set one state value."""
        self.state[key] = value


def rng_for(seed: int) -> np.random.Generator:
    """Return a fresh central generator for the given run seed."""
    return np.random.default_rng(seed)


# Rule-step tests: distribution helpers inside conditions and then/else blocks.

def rng_for(seed: int) -> np.random.Generator:
    """Return a fresh central generator for the given run seed."""
    return np.random.default_rng(seed)


def make_agent(agent_id: str = "a1", **state) -> "AgentState":
    """Create an AgentState of type 'agent' with the given state."""
    return AgentState(agent_id=agent_id, agent_type_name="agent", state=dict(state))


def test_helper_in_then_expression():
    agent = make_agent(flag=True, count=0)
    steps = build_rule_steps(
        [
            {
                "condition": 'state["flag"]',
                "then": [{"field": "count", "expression": "binomial(10, 1.0)"}],
                "else": [],
            }
        ],
        topology_names=[],
    )
    run_rule_steps(steps, agent, lambda *_a: [], rng=rng_for(1))
    assert agent.get("count") == 10


def test_helper_in_condition_combined_with_neighbour_helper():
    """The neighbour-aware condition path also forwards rng."""
    agent = make_agent(alert=False)
    neighbours = [
        AgentState(agent_id="n1", agent_type_name="agent", state={"status": "I"}),
        AgentState(agent_id="n2", agent_type_name="agent", state={"status": "S"}),
    ]
    steps = build_rule_steps(
        [
            {
                "condition": (
                    """neighbor_count('state["status"] == "I"') > 0 """
                    "and random() < 1.0"
                ),
                "then": [{"field": "alert", "expression": "True"}],
                "else": [],
            }
        ],
        topology_names=[],
    )
    run_rule_steps(steps, agent, lambda *_a: neighbours, rng=rng_for(1))
    assert agent.get("alert") is True


def test_rule_without_rng_rejects_helpers():
    agent = make_agent(alert=False)
    steps = build_rule_steps(
        [
            {
                "condition": "random() < 0.5",
                "then": [{"field": "alert", "expression": "True"}],
                "else": [],
            }
        ],
        topology_names=[],
    )
    with pytest.raises(ValueError):
        run_rule_steps(steps, agent, lambda *_a: [])


def test_rule_steps_same_run_seed_same_outcomes():
    """Unseeded helper draws across many agents repeat for the same run seed."""
    steps = build_rule_steps(
        [
            {
                "condition": "random() < 0.5",
                "then": [{"field": "infected", "expression": "True"}],
                "else": [],
            }
        ],
        topology_names=[],
    )

    def run(seed: int) -> list[bool]:
        rng = rng_for(seed)
        agents = [make_agent(f"a{i}", infected=False) for i in range(50)]
        for agent in agents:
            run_rule_steps(steps, agent, lambda *_a: [], rng=rng)
        return [a.get("infected") for a in agents]

    assert run(5) == run(5)
    assert run(5) != run(6)


# Each variant exercises a different evaluation path inside run_step.
BEHAVIOUR_VARIANTS = {
    # plain step -> run_rule_steps -> evaluate_step -> _safe_eval
    "plain_step": [
        {"field": "age", "expression": "state['age'] + binomial(5, 0.5)"},
    ],
    # conditional -> run_rule_steps -> _evaluate_condition, then block
    "conditional": [
        {
            "condition": "random() < 0.5",
            "then": [{"field": "age", "expression": "state['age'] + 1"}],
            "else": [],
        },
    ],
    # legacy single-string path -> evaluate_expression
    "legacy": [
        {
            "expression": 'state["age"] += binomial(5, 0.5)',
            "topology_name": "contact",
        },
    ],
}


def final_ages(sim: "Simulation") -> list[Any]:
    """Return every agent's final age in creation order (ids are random UUIDs)."""
    return [agent.get("age") for agent in sim.live_population.values()]


def run_config(
        base_config: dict,
        seed: int,
        behaviours: list[dict],
        n: int = 30,
        steps: int = 5,
) -> list[Any]:
    """Build and run a simulation from base_config with the given run seed.

    Args:
        base_config: the conftest fixture (copied, never mutated).
        seed: top-level run seed.
        behaviours: behaviour entries for the "person" agent type.
        n: number of agents.
        steps: number of steps to run.

    Returns:
        Final ages of all agents.
    """
    config = copy.deepcopy(base_config)
    config["seed"] = seed
    config["agent_types"][0]["count"] = n
    config["agent_types"][0]["attributes"][0]["distribution"] = {
        "kind": "fixed",
        "value": 18,
    }
    config["behaviours"] = {"person": behaviours}
    config["stopping"]["max_steps"] = steps
    sim = Simulation.from_config(config)
    sim()
    return final_ages(sim)


@pytest.mark.parametrize("variant", BEHAVIOUR_VARIANTS)
def test_unseeded_helpers_repeat_for_same_run_seed(base_config, variant):
    behaviours = BEHAVIOUR_VARIANTS[variant]
    assert run_config(base_config, 1, behaviours) == run_config(base_config, 1, behaviours)


@pytest.mark.parametrize("variant", BEHAVIOUR_VARIANTS)
def test_unseeded_helpers_change_with_run_seed(base_config, variant):
    behaviours = BEHAVIOUR_VARIANTS[variant]
    assert run_config(base_config, 1, behaviours) != run_config(base_config, 2, behaviours)


def test_unseeded_helpers_draw_independently_per_agent(base_config):
    ages = run_config(base_config, 1, BEHAVIOUR_VARIANTS["plain_step"])
    assert len(set(ages)) > 1  # agents did not all receive the same draws


def test_seeded_helper_ignores_run_seed_and_is_identical_per_agent(base_config):
    behaviours = [
        {"field": "age", "expression": "state['age'] + binomial(5, 0.5, seed=3)"},
    ]
    first = run_config(base_config, 1, behaviours)
    second = run_config(base_config, 2, behaviours)
    assert first == second  # independent of the top-level run seed
    assert len(set(first)) == 1  # every agent drew the same seeded value


def build_sim(
        base_config: dict,
        seed: int,
        behaviours: list[dict],
        n: int = 30,
        steps: int = 5,
        **config_overrides,
) -> "Simulation":
    """Build (but do not run) a simulation from base_config.

    Ages start fixed at 18 for every agent, so differences between runs come
    only from helper draws.

    Args:
        base_config: the conftest fixture (copied, never mutated).
        seed: top-level run seed.
        behaviours: behaviour entries for the "person" agent type.
        n: number of agents.
        steps: max_steps for the run.
        **config_overrides: top-level config keys to replace, e.g.
            ``sandbox={...}`` or ``stopping={...}``.

    Returns:
        The constructed Simulation.
    """
    config = copy.deepcopy(base_config)
    config["seed"] = seed
    config["agent_types"][0]["count"] = n
    config["agent_types"][0]["attributes"][0]["distribution"] = {
        "kind": "fixed",
        "value": 18,
    }
    config["behaviours"] = {"person": behaviours}
    config["stopping"]["max_steps"] = steps
    config.update(config_overrides)
    return Simulation.from_config(config)


# Helpers inside comprehensions over the contact topology (all_pairs).
COMPREHENSION_VARIANTS = {
    "plain_step": [
        {
            "field": "age",
            "expression": "state['age'] + len([n for n in neighbours if random() < 0.2])",
        },
    ],
    "then_block": [
        {
            "condition": "state['age'] >= 0",
            "then": [
                {
                    "field": "age",
                    "expression": (
                        "state['age'] + len([n for n in neighbours if random() < 0.2])"
                    ),
                },
            ],
            "else": [],
        },
    ],
}


def run_with_sandbox(base_config: dict, seed: int, behaviours: list[dict]) -> list:
    """Run with a neighbour cap high enough for all_pairs over 30 agents."""
    sim = build_sim(base_config, seed, behaviours, sandbox={"max_neighbours": 100})
    sim()
    return final_ages(sim)


@pytest.mark.parametrize("variant", COMPREHENSION_VARIANTS)
def test_helper_in_comprehension_repeats_for_same_run_seed(base_config, variant):
    behaviours = COMPREHENSION_VARIANTS[variant]
    first = run_with_sandbox(base_config, 1, behaviours)
    second = run_with_sandbox(base_config, 1, behaviours)
    assert first == second
    assert any(age > 18 for age in first)  # the comprehension actually drew


@pytest.mark.parametrize("variant", COMPREHENSION_VARIANTS)
def test_helper_in_comprehension_changes_with_run_seed(base_config, variant):
    behaviours = COMPREHENSION_VARIANTS[variant]
    assert run_with_sandbox(base_config, 1, behaviours) != run_with_sandbox(
        base_config, 2, behaviours
    )


# ---- error paths ----------------------------------------------------------


def test_unknown_helper_is_rejected_in_a_run(base_config):
    """The helper set is closed: exponential is not available until registered."""
    sim = build_sim(
        base_config, 1, [{"field": "age", "expression": "state['age'] + exponential(1.0)"}]
    )
    with pytest.raises(ValueError, match="exponential"):
        sim()


def test_invalid_helper_arguments_surface_as_value_error(base_config):
    sim = build_sim(
        base_config, 1, [{"field": "age", "expression": "state['age'] + binomial(5, 2)"}]
    )
    with pytest.raises(ValueError, match="binomial"):
        sim()


# ---- stopping conditions --------------------------------------------------


def test_stopping_condition_does_not_get_distribution_helpers(base_config):
    """Stopping conditions use their own evaluator and are given no rng.

    A condition calling random() cannot evaluate, so check_stopping records
    the failure as a stop with reason 'error' at the end of the first step.
    """
    sim = build_sim(
        base_config,
        1,
        [{"field": "age", "expression": "state['age'] + 1"}],
        stopping={"max_steps": 5, "conditions": ["random() < 0.5"], "combinator": "OR"},
    )
    result = sim()

    assert result.stopped is True
    assert result.reason == "error"
    assert "random" in result.detail