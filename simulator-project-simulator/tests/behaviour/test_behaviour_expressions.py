import pytest
import numpy as np
import uuid
import random
import logging
import copy
from simpleeval import EvalWithCompoundTypes
from typing import Any
from types import SimpleNamespace

from behaviour.expressions import evaluate_expression, run_rule_steps, _safe_eval, _uses_neighbours
from behaviour.expression_steps import build_rule_steps, calls_neighbour_helper
from behaviour.expression_comprehensions import (
    ComprehensionDepthError,
    NeighborSetTooLargeError,
    analyse_expression,
    build_views_from_states,
    SandboxConfig,
    check_comprehension_policy,
    check_neighbour_cap,
    reset_policy_caches,
)
from behaviour import expression_distributions as dist  # for monkey patching
from behaviour.expression_distributions import (
    available_distributions,
    build_distribution_functions,
    distribution,
)
from behaviour.condition import _evaluate_condition
from behaviour.neighbour_helpers import make_neighbour_helpers
from runner.simulation import Simulation
from runner.state import AgentState
from stopping.expression import evaluate_condition

def test_evaluate_expression_success(sample_agents_dict):
    cmd_ls = ['state["energy"] -= 1', 'state["energy"] += 1', 'state["energy"] *= 3', 'state["energy"] /= 2', 'state["energy"] = 2.1']
    results = []

    i = 0
    for id, agent_state in sample_agents_dict.items():
        agent_state.state["energy"] = 1  # Set the energy value instead of random
        evaluate_expression(cmd_ls[(i+1)%len(cmd_ls)-1], agent_state, None)
        results.append((cmd_ls[(i+1)%len(cmd_ls)-1], sample_agents_dict[id]))
        i += 1

    for result in results:
        if result[0] == cmd_ls[0]:
            assert result[1].state["energy"] == 0
        elif result[0] == cmd_ls[1]:
            assert result[1].state["energy"] == 2
        elif result[0] == cmd_ls[2]:
            assert result[1].state["energy"] == 3
        elif result[0] == cmd_ls[3]:
            assert result[1].state["energy"] == 0.5
        elif result[0] == cmd_ls[4]:
            assert result[1].state["energy"] == 2.1

def test_evaluate_expression_with_network_success(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    target_agent.state["infected"] = False
    neighbour_1 = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={"infected": False})
    neighbour_2 = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={"infected": True})
    neighbours_state = [neighbour_1.state, neighbour_2.state]
    evaluate_expression('state["infected"] = any(n["infected"] for n in neighbours)', target_agent, neighbours_state)

    assert target_agent.state["infected"] == True

def test_evaluate_expression_invalid_expr_throws_value_error(sample_agents_dict):
    cmd_ls = ['state["energy"] m= 1', 'state["energy"] p= 1', 'state["energy"] t= 3', 'state["energy"] d= 2',
              'state["energy"] == 2.1']
    results = []

    i = 0
    with pytest.raises(ValueError) as e:
        for id, agent_state in sample_agents_dict.items():
            agent_state.state["energy"] = 1  # Set the energy value instead of random
            evaluate_expression(cmd_ls[(i + 1) % len(cmd_ls) - 1], agent_state, None)
            results.append((cmd_ls[(i + 1) % len(cmd_ls) - 1], sample_agents_dict[id]))
            i += 1

def test_evaluate_expression_divide_zero_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] /= 0', agent, [])

def test_evaluate_expression_syntax_error_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    agent.state["energy"] = 10
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] += 1 +', agent, [])

def test_evaluate_expression_type_error_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    agent.state["energy"] = 10
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] += "abc"', agent, [])

def test_evaluate_expression_undefined_name_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] = undefined_variable', agent, [])

"""
Ternary (conditional) expression tests for the shared simpleeval sandbox,
exercised through the S-10 stopping-condition evaluator.
"""

def make_agent(**attributes: Any) -> AgentState:
    """Build an AgentState carrying the given attributes for condition tests.

    Args:
        **attributes: Attribute name/value pairs stored in ``AgentState.state``,
            e.g. ``status="I"``, ``age=40``.

    Returns:
        A valid AgentState whose ``state`` dict holds the given attributes.
    """
    return AgentState(agent_type_name="person", state=dict(attributes))


# --- Single ternary ---------------------------------------------------------


@pytest.mark.parametrize(
    "status, age, expected",
    [
        ("I", 10, True),   # test true  -> body (True)
        ("S", 70, True),   # test false -> orelse (age > 60)
        ("S", 30, False),  # test false -> orelse (age > 60)
    ],
)
def test_single_ternary(status: str, age: int, expected: bool) -> None:
    """A single ternary selects the correct branch and returns a bool."""
    agent = make_agent(status=status, age=age)
    expr = "True if state['status'] == 'I' else state['age'] > 60"
    assert _evaluate_condition(expr, agent) is expected


# --- Nested ternary ---------------------------------------------------------


@pytest.mark.parametrize(
    "status, age, expected",
    [
        ("S", 10, True),   # first test true  -> age < 18
        ("S", 40, False),  # first test true  -> age < 18
        ("E", 40, True),   # second test true -> age < 65
        ("E", 70, False),  # second test true -> age < 65
        ("I", 40, False),  # fallthrough      -> False
    ],
)
def test_nested_ternary(status: str, age: int, expected: bool) -> None:
    """a if c1 else b if c2 else c resolves right-associatively."""
    expr = (
        "state['age'] < 18 if state['status'] == 'S' "
        "else state['age'] < 65 if state['status'] == 'E' else False"
    )
    assert _evaluate_condition(expr, make_agent(status=status, age=age)) is expected


def test_nested_ternary_has_no_depth_cap() -> None:
    """Deeply nested ternaries are not rejected by the sandbox."""
    depth = 30
    chain = (
        "".join(f"True if state['age'] == {i} else " for i in range(1, depth + 1))
        + "False"
    )
    assert _evaluate_condition(chain, make_agent(age=depth)) is True
    assert _evaluate_condition(chain, make_agent(age=depth + 1)) is False


# --- Short-circuiting and composition ---------------------------------------


def test_unused_branch_not_evaluated() -> None:
    """The branch not taken is never evaluated (no ZeroDivisionError)."""
    agent = make_agent(age=0)
    expr = "True if state['age'] == 0 else 10 / state['age'] > 1"
    assert _evaluate_condition(expr, agent) is True


def test_ternary_combined_with_boolean_operators() -> None:
    """Ternary composes with and/or when parenthesised."""
    agent = make_agent(status="I", age=40)
    expr = "(True if state['status'] == 'I' else False) and state['age'] > 18"
    assert _evaluate_condition(expr, agent) is True


# --- Sandbox still enforced inside ternaries --------------------------------


def test_unsafe_call_in_taken_branch_still_blocked() -> None:
    """Sandbox restrictions still apply to a ternary branch that is evaluated."""
    with pytest.raises(ValueError):
        _evaluate_condition("__import__('os') if True else False", make_agent(age=1))


def test_non_bool_ternary_result_rejected() -> None:
    """A ternary that yields a non-bool is rejected, like any other condition."""
    with pytest.raises(ValueError):
        _evaluate_condition("'a' if True else 'b'", make_agent(age=1))

class FakeModel:
    """Minimal stand-in for the model object passed to S-10 conditions."""

    def __init__(self, counts: dict[str, int]) -> None:
        """Store canned ``count`` results.

        Args:
            counts: Mapping of count-expression -> number of matching agents.
        """
        self._counts = counts

    def count(self, expr: str) -> int:
        """Return the canned count for ``expr`` (0 if unknown).

        Args:
            expr: The agent-selection expression, e.g. ``"status==I"``.

        Returns:
            The number of agents matching ``expr``.
        """
        return self._counts.get(expr, 0)


def test_ternary_with_model_count_true_branch() -> None:
    """A ternary whose test uses model.count() takes the body when the test holds."""
    model = FakeModel({"status==I": 0, "status==S": 5})
    expr = 'True if model.count("status==I") == 0 else model.count("status==S") == 0'
    assert evaluate_condition(expr, model) is True


def test_ternary_with_model_count_false_branch() -> None:
    """The orelse branch is taken when the count-based test fails."""
    model = FakeModel({"status==I": 3, "status==S": 0})
    expr = 'False if model.count("status==I") == 0 else model.count("status==S") == 0'
    assert evaluate_condition(expr, model) is True


def test_nested_ternary_with_model_count() -> None:
    """Nested ternaries can chain several model.count() checks."""
    model = FakeModel({"status==I": 2, "status==E": 0})
    expr = (
        'False if model.count("status==I") == 0 '
        'else True if model.count("status==E") == 0 else False'
    )
    assert evaluate_condition(expr, model) is True

# ----------------------------------
# Test conditional with neighbours
# ----------------------------------

GAIN_STEP = [
    {
        "field": "energy",
        "expression": (
            "state['energy'] + 0.1 * max(0, "
            "sum(n['energy'] for n in neighbours) / len(neighbours)"
            " - state['energy']) if len(neighbours) > 0 "
            "else state['energy']"
        ),
        "topology_name": "contact",
    }
]


def _run(own_energy: float, neighbour_energies: list[float]) -> float:
    """Run the gain step for one agent and return its resulting energy."""
    agent = AgentState(
        agent_id="a1", agent_type_name="agent", state={"energy": own_energy}
    )
    neighbours = [
        AgentState(agent_id=f"n{i}", agent_type_name="agent", state={"energy": e})
        for i, e in enumerate(neighbour_energies)
    ]
    steps = build_rule_steps(GAIN_STEP, topology_names=["contact"])
    run_rule_steps(steps, agent, lambda _t: neighbours)
    return agent.get("energy")


def test_gains_when_neighbours_are_richer():
    # neighbour mean 80, own 60 -> 60 + 0.1 * 20
    assert _run(60.0, [80.0, 80.0]) == 62.0


def test_no_change_when_neighbours_are_poorer():
    assert _run(60.0, [40.0, 40.0]) == 60.0


# -------------------
# Neighbour helpers
# -------------------

def test_condition_can_use_neighbour_helper():
    agent = AgentState(
        agent_id="a1", agent_type_name="agent", state={"alert": False}
    )
    neighbours = [
        AgentState(agent_id="n1", agent_type_name="agent", state={"status": "I"}),
        AgentState(agent_id="n2", agent_type_name="agent", state={"status": "S"}),
    ]
    steps = build_rule_steps(
        [
            {
                "condition": """neighbor_count('state["status"] == "I"') > 0""",
                "then": [{"field": "alert", "expression": "True"}],
                "else": [],
            }
        ],
        topology_names=[],
    )

    run_rule_steps(steps, agent, lambda _t: neighbours)

    assert agent.get("alert") is True

@pytest.mark.parametrize(
    "expression, expected",
    [
        ("neighbor_count('state[\"x\"] > 1') > 0", True),   # helper call
        ("sum(n['e'] for n in neighbours)", True),          # `neighbours` name
        ("state['neighbor_count'] + 1", False),             # substring only, no Call
        ("state['energy'] - 0.5", False),
    ],
)
def test_calls_neighbour_helper_detection(expression, expected):
    assert calls_neighbour_helper(expression) is expected


def test_neighbours_name_requires_topology_with_two_topologies():
    raw = [{"field": "e", "expression": "sum(n['e'] for n in neighbours)"}]

    build_rule_steps(raw, topology_names=["a"])  # one topology: fine
    with pytest.raises(ValueError):
        build_rule_steps(raw, topology_names=["a", "b"])

THREE_LEVEL = (
    "[o['status'] for n in neighbours for m in n['neighbours'] "
    "for o in m['neighbours']]"
)


@pytest.fixture(autouse=True)
def _reset_policy_caches():
    """Start each test with an empty warn-once set and analysis cache."""
    reset_policy_caches()
    yield
    reset_policy_caches()


@pytest.fixture
def graph():
    """Focal 'a' with neighbours b, c; b's neighbours are a, d, e.

    Returns a namespace with ``focal`` (the focal agent), ``neighbours_of``
    (agent id -> neighbour agents) and ``views`` (hop-0 AgentViews with lazy
    deeper hops).
    """
    statuses = {"a": "S", "b": "I", "c": "S", "d": "I", "e": "S"}
    agents = {
        k: SimpleNamespace(agent_id=k, state={"status": v})
        for k, v in statuses.items()
    }
    adjacency = {"a": ["b", "c"], "b": ["a", "d", "e"], "c": ["a"]}

    def neighbours_of(aid):
        return [agents[i] for i in adjacency.get(aid, [])]

    return SimpleNamespace(
        focal=agents["a"],
        neighbours_of=neighbours_of,
        views=build_views_from_states(neighbours_of("a"), neighbours_of),
    )


# --- evaluation through _safe_eval ------------------------------------------

@pytest.mark.parametrize(
    "name, key",
    [
        ("neighbors", "neighbors"),
        ("neighbours", "neighbours"),
        ("neighbors", "neighbours"),
        ("neighbours", "neighbors"),
    ],
)
def test_both_spellings_behave_identically(graph, name, key):
    """Either spelling works as the name and as the nested key."""
    expr = f"[m['status'] for n in {name} for m in n['{key}']]"
    assert _safe_eval(expr, graph.focal, graph.views) == ["S", "I", "S", "S"]


def test_single_level_comprehension(graph):
    expr = "[n['status'] for n in neighbours]"
    assert _safe_eval(expr, graph.focal, graph.views) == ["I", "S"]


def test_two_hop_beyond_evaluates_by_default(graph):
    """Soft limit only: nesting past one hop warns but still evaluates."""
    assert _safe_eval(THREE_LEVEL, graph.focal, graph.views) == ["I", "S", "I", "S"]


def test_two_hop_beyond_rejected_when_hard_cap_configured(graph):
    with pytest.raises(ComprehensionDepthError):
        _safe_eval(
            THREE_LEVEL, graph.focal, graph.views, sandbox=SandboxConfig(max_hops=1)
        )


def test_comprehension_over_no_neighbours_is_empty(graph):
    assert _safe_eval("[n['status'] for n in neighbours]", graph.focal, []) == []
    assert _evaluate_condition(
        "len([n for n in neighbours]) == 0", graph.focal, []
    ) is True


def test_condition_neighbour_cap_from_config(graph):
    expr = "len([n for n in neighbours]) > 0"
    with pytest.raises(NeighborSetTooLargeError):
        _evaluate_condition(
            expr, graph.focal, graph.neighbours_of("a"),
            sandbox=SandboxConfig(max_neighbours=1),  # 'a' has 2 neighbours
        )


def test_condition_hard_hop_cap(graph):
    expr = (
        "len([o for n in neighbours for m in n['neighbours'] "
        "for o in m['neighbours']]) > 0"
    )
    with pytest.raises(ComprehensionDepthError):
        _evaluate_condition(
            expr, graph.focal, graph.neighbours_of("a"),
            neighbours_of=graph.neighbours_of,
            sandbox=SandboxConfig(max_hops=1),
        )


# --- hop analysis ------------------------------------------------------------

@pytest.mark.parametrize("nb", ["neighbors", "neighbours"])
@pytest.mark.parametrize(
    "template, hop",
    [
        ("[n for n in {nb}]", 0),
        ("[m for n in {nb} for m in n['{nb}']]", 1),
        ("[[m for m in n['{nb}']] for n in {nb}]", 1),
        ("max(len(n['{nb}']) for n in {nb})", 1),  # needs the _max_hop fix
        ("[o for n in {nb} for m in n['{nb}'] for o in m['{nb}']]", 2),
        ("[x for x in range(3)]", -1),
    ],
)
def test_hop_analysis(template, hop, nb):
    assert analyse_expression(template.format(nb=nb)).max_hop == hop


# --- warn once ---------------------------------------------------------------

def _hop_warnings(caplog):
    return [r for r in caplog.records if "hops beyond" in r.message]


def test_hop_warning_logged_once_per_expression(caplog):
    with caplog.at_level(logging.WARNING, logger="simulator"):
        first = check_comprehension_policy(THREE_LEVEL)
        second = check_comprehension_policy(THREE_LEVEL)
    assert len(_hop_warnings(caplog)) == 1
    assert first.warnings and second.warnings  # still available for the UI


def test_hop_warning_logged_again_for_a_different_expression(caplog):
    other = (
        "[p['status'] for n in neighbours for m in n['neighbours'] "
        "for p in m['neighbours']]"
    )
    with caplog.at_level(logging.WARNING, logger="simulator"):
        check_comprehension_policy(THREE_LEVEL)
        check_comprehension_policy(other)
    assert len(_hop_warnings(caplog)) == 2


# --- caps and config ---------------------------------------------------------

def test_neighbour_cap_uses_configured_value():
    sandbox = SandboxConfig(max_neighbours=3)
    check_neighbour_cap([{}, {}, {}], sandbox.max_neighbours)  # at the cap: fine
    with pytest.raises(NeighborSetTooLargeError):
        check_neighbour_cap([{}, {}, {}, {}], sandbox.max_neighbours, agent_id="a")


def test_sandbox_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        SandboxConfig(max_neighbours=0)


def test_to_config_round_trips_sandbox_limits(base_config):
    """A custom sandbox section survives from_config -> to_config."""
    base_config["sandbox"] = {"max_neighbours": 5000}
    out = Simulation.from_config(base_config).to_config()
    assert out["sandbox"]["max_neighbours"] == 5000
    assert out["sandbox"]["max_hops"] is None


def test_sandbox_cap_reaches_expression_evaluation(base_config):
    """max_neighbours from the config must stop an oversized comprehension."""
    base_config["sandbox"] = {"max_neighbours": 1}
    base_config["behaviours"] = {
        "person": [
            {
                "expression": 'state["age"] += len([n for n in neighbours])',
                "topology_name": "contact",
            }
        ]
    }
    sim = Simulation.from_config(base_config)
    with pytest.raises(ValueError, match="capped at 1"):
        sim()


def test_one_hop_beyond_works_on_the_rule_path(base_config):
    """n['neighbours'] must work through the rule path (plain dicts there
    would raise KeyError)."""
    base_config["behaviours"] = {
        "person": [
            {
                "field": "age",
                "expression": (
                    "state['age'] + len([m for n in neighbours "
                    "for m in n['neighbours']])"
                ),
                "topology_name": "contact",
            }
        ]
    }
    sim = Simulation.from_config(base_config)
    result = sim()
    assert result.stopped is True
    assert result.reason == "max_steps"
    assert all(a.state["age"] >= 3 for a in sim.live_population.values())


# --- views -------------------------------------------------------------------

def test_views_expose_one_hop_beyond(graph):
    assert [v["status"] for v in graph.views] == ["I", "S"]
    assert [m["status"] for m in graph.views[0]["neighbours"]] == ["S", "I", "S"]


def test_deeper_hop_is_capped(graph):
    views = build_views_from_states(
        graph.neighbours_of("a"), graph.neighbours_of, max_neighbors=2
    )
    with pytest.raises(NeighborSetTooLargeError):
        views[0]["neighbours"]  # b has 3 neighbours


# --- conditions --------------------------------------------------------------

@pytest.mark.parametrize("name", ["neighbours", "neighbors"])
def test_condition_reaches_one_hop_beyond(graph, name):
    expr = f"len([m for n in {name} for m in n['{name}'] if m['status'] == 'I']) >= 1"
    assert _evaluate_condition(
        expr,
        graph.focal,
        graph.neighbours_of("a"),
        neighbours_of=graph.neighbours_of,
    ) is True


def test_uses_neighbours_accepts_both_spellings():
    assert _uses_neighbours("len([n for n in neighbors]) > 0")
    assert _uses_neighbours("len([n for n in neighbours]) > 0")


# ----------------------------------------
# Helper function in list comprehension
# ----------------------------------------

class FakeAgent:
    """Minimal AgentState stand-in: agent_id, state dict and get()."""

    def __init__(self, agent_id, **state):
        self.agent_id = agent_id
        self.state = dict(state)

    def get(self, key):
        """Return the attribute value, as AgentState.get does."""
        return self.state[key]


@pytest.fixture
def focal_and_neighbours():
    """Focal agent plus three neighbours: b (I, 60), c (S, 40), d (I, 50)."""
    focal = FakeAgent("a", status="S", energy=10)
    neighbours = [
        FakeAgent("b", status="I", energy=60),
        FakeAgent("c", status="S", energy=40),
        FakeAgent("d", status="I", energy=50),
    ]
    return focal, neighbours


def evaluate(expr, focal, neighbours):
    """Evaluate ``expr`` the way evaluate_step does, with the real helpers."""
    return _safe_eval(
        expr,
        focal,
        [a.state for a in neighbours],
        make_neighbour_helpers(neighbours),
    )


def test_helper_inside_comprehension(focal_and_neighbours):
    focal, neighbours = focal_and_neighbours
    expr = '''[neighbor_count('state["status"] == "I"') for n in neighbours]'''
    # Helpers are bound to the focal agent's neighbours, so every iteration
    # sees the same count; n is not involved.
    assert evaluate(expr, focal, neighbours) == [2, 2, 2]


def test_helper_and_comprehension_variable_together(focal_and_neighbours):
    focal, neighbours = focal_and_neighbours
    expr = '''[n['energy'] + neighbor_count('state["status"] == "I"') for n in neighbours]'''
    assert evaluate(expr, focal, neighbours) == [62, 42, 52]


def test_helper_and_comprehension_in_one_expression(focal_and_neighbours):
    focal, neighbours = focal_and_neighbours
    expr = (
        '''neighbor_sum('energy', 'state["status"] == "I"') '''
        '''+ sum(n['energy'] for n in neighbours if n['status'] == 'S')'''
    )
    assert evaluate(expr, focal, neighbours) == 150  # (60 + 50) + 40


def test_filter_without_state_prefix_is_rejected(focal_and_neighbours):
    focal, neighbours = focal_and_neighbours
    expr = '''[neighbor_count('status == "I"') for n in neighbours]'''
    with pytest.raises(ValueError):
        evaluate(expr, focal, neighbours)


# sandbox must not leak through the new nodes


@pytest.mark.parametrize(
    "expr",
    [
        "[n.__class__ for n in neighbours]",
        "[().__class__.__mro__ for n in neighbours]",
        "[__import__('os') for n in neighbours]",
    ],
)
def test_comprehension_cannot_reach_dunders_or_imports(graph, expr):
    with pytest.raises(ValueError):
        _safe_eval(expr, graph.focal, graph.views)

"""
RNG
"""

N_SAMPLES = 20_000


def make_helpers(run_seed: int = 42) -> dict:
    """Build helpers bound to a fresh RNG for the given run seed."""
    return build_distribution_functions(np.random.default_rng(run_seed))


def simulate_run(run_seed: int) -> list:
    """Mimic a full run: a fixed sequence of unseeded draws."""
    h = make_helpers(run_seed)
    out = []
    for _ in range(50):
        out += [h["random"](), h["normal"](0, 1), h["binomial"](10, 0.5), h["poisson"](3)]
    return out


# ---- registry -------------------------------------------------------------


def test_helper_set_is_fixed():
    assert set(available_distributions()) == {"random", "normal", "binomial", "poisson"}
    assert set(make_helpers()) == set(available_distributions())


def test_extension_via_registry(monkeypatch):
    monkeypatch.setattr(dist, "_REGISTRY", dict(dist._REGISTRY))

    @distribution("exponential")
    def _exponential(rng, scale):
        return float(rng.exponential(scale))

    h = make_helpers()
    assert h["exponential"](2.0, seed=1) == h["exponential"](2.0, seed=1)


# ---- determinism ----------------------------------------------------------


def test_unseeded_deterministic_across_full_runs():
    assert simulate_run(123) == simulate_run(123)


def test_unseeded_differs_for_different_run_seed():
    assert simulate_run(123) != simulate_run(124)


@pytest.mark.parametrize(
    "name,args",
    [("random", ()), ("normal", (0, 1)), ("binomial", (10, 0.5)), ("poisson", (3,))],
)
def test_seeded_deterministic_per_invocation(name, args):
    h = make_helpers()
    first = h[name](*args, seed=7)
    assert all(h[name](*args, seed=7) == first for _ in range(20))
    assert h[name](*args, 7) == first  # positional seed form


def test_seeded_independent_of_run_seed():
    assert make_helpers(1)["normal"](0, 1, seed=7) == make_helpers(2)["normal"](0, 1, seed=7)


def test_seeded_calls_do_not_advance_shared_stream():
    plain, mixed = make_helpers(5), make_helpers(5)
    expected = [plain["random"]() for _ in range(10)]
    actual = []
    for _ in range(10):
        mixed["random"](seed=99)
        actual.append(mixed["random"]())
    assert actual == expected


def test_different_seeds_give_different_values():
    h = make_helpers()
    assert h["random"](seed=1) != h["random"](seed=2)


# ---- distribution shape (fixed seed, so these cannot flake) ----------------


def test_random_shape():
    h = make_helpers(2024)
    xs = np.array([h["random"]() for _ in range(N_SAMPLES)])
    assert xs.min() >= 0.0 and xs.max() < 1.0
    assert xs.mean() == pytest.approx(0.5, abs=0.02)


def test_normal_shape():
    h = make_helpers(2024)
    xs = np.array([h["normal"](10, 2) for _ in range(N_SAMPLES)])
    assert xs.mean() == pytest.approx(10, abs=0.1)
    assert xs.std() == pytest.approx(2, abs=0.1)


def test_binomial_shape():
    h = make_helpers(2024)
    xs = np.array([h["binomial"](20, 0.3) for _ in range(N_SAMPLES)])
    assert xs.min() >= 0 and xs.max() <= 20
    assert xs.mean() == pytest.approx(6.0, abs=0.1)
    assert xs.var() == pytest.approx(4.2, abs=0.3)


def test_poisson_shape():
    h = make_helpers(2024)
    xs = np.array([h["poisson"](4) for _ in range(N_SAMPLES)])
    assert xs.min() >= 0
    assert xs.mean() == pytest.approx(4.0, abs=0.1)
    assert xs.var() == pytest.approx(4.0, abs=0.3)


def test_return_types_are_native_python():
    h = make_helpers()
    assert type(h["random"]()) is float
    assert type(h["normal"](0, 1)) is float
    assert type(h["binomial"](5, 0.5)) is int
    assert type(h["poisson"](2)) is int


# ---- validation -----------------------------------------------------------


@pytest.mark.parametrize(
    "name,args",
    [
        ("normal", (0, -1)),
        ("normal", (0, float("nan"))),
        ("binomial", (-1, 0.5)),
        ("binomial", (5.5, 0.5)),
        ("binomial", (5, 1.5)),
        ("binomial", (5, float("nan"))),
        ("poisson", (-0.1,)),
    ],
)
def test_invalid_arguments_raise_value_error(name, args):
    with pytest.raises(ValueError):
        make_helpers()[name](*args)


@pytest.mark.parametrize("bad_seed", ["abc", 1.5, True])
def test_invalid_seed_raises_type_error(bad_seed):
    with pytest.raises(TypeError):
        make_helpers()["random"](seed=bad_seed)


def test_wrong_arity_raises_type_error():
    with pytest.raises(TypeError):
        make_helpers()["normal"](0)
    with pytest.raises(TypeError):
        make_helpers()["normal"](0, 1, 2, 3)
    with pytest.raises(TypeError):
        make_helpers()["normal"](0, 1, 2, seed=3)  # seed given twice


# ---- inside the sandbox ---------------------------------------------------


def make_evaluator(names: dict | None = None, run_seed: int = 42) -> EvalWithCompoundTypes:
    """Sandbox evaluator with the distribution helpers installed."""
    return EvalWithCompoundTypes(
        names=names or {}, functions=make_helpers(run_seed)
    )


def test_helpers_usable_in_ternary():
    ev = make_evaluator()
    assert ev.eval("1 if random(seed=3) < 2 else 0") == 1


def test_helpers_usable_in_comprehension_unseeded_are_independent():
    ev = make_evaluator({"neighbours": list(range(50))})
    draws = ev.eval("[random() for n in neighbours]")
    assert len(set(draws)) == 50


def test_seeded_in_comprehension_repeats_same_value():
    ev = make_evaluator({"neighbours": list(range(10))})
    draws = ev.eval("[random(seed=5) for n in neighbours]")
    assert len(set(draws)) == 1


def test_comprehension_infection_pattern_is_run_deterministic():
    """The same run seed yields the same infected set from a comprehension."""
    expr = "[n for n in neighbours if random() < 0.3]"
    names = {"neighbours": list(range(200))}
    first = make_evaluator(names, 9).eval(expr)
    second = make_evaluator(names, 9).eval(expr)
    assert first == second
    assert 0 < len(first) < 200


def test_unknown_helper_is_not_available():
    from simpleeval import FunctionNotDefined

    with pytest.raises(FunctionNotDefined):
        make_evaluator().eval("exponential(1.0)")

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


# ---- _safe_eval -----------------------------------------------------------


def test_safe_eval_helpers_available_with_rng():
    value = _safe_eval("random()", StubAgent({}), [], rng=rng_for(1))
    assert isinstance(value, float) and 0.0 <= value < 1.0


def test_safe_eval_same_run_seed_same_draws():
    expr = "[random(), normal(0, 1), binomial(10, 0.5), poisson(3)]"
    first = _safe_eval(expr, StubAgent({}), [], rng=rng_for(7))
    second = _safe_eval(expr, StubAgent({}), [], rng=rng_for(7))
    assert first == second


def test_safe_eval_without_rng_rejects_helpers():
    with pytest.raises(ValueError):
        _safe_eval("random()", StubAgent({}), [])


def test_safe_eval_without_rng_rejects_seeded_helpers_too():
    with pytest.raises(ValueError):
        _safe_eval("random(seed=1)", StubAgent({}), [])


def test_safe_eval_seeded_call_leaves_shared_stream_untouched():
    plain, mixed = rng_for(3), rng_for(3)
    expected = _safe_eval("random()", StubAgent({}), [], rng=plain)
    _safe_eval("random(seed=99)", StubAgent({}), [], rng=mixed)
    actual = _safe_eval("random()", StubAgent({}), [], rng=mixed)
    assert actual == expected


def test_safe_eval_comprehension_over_neighbours_is_run_deterministic():
    """The same run seed selects the same neighbours from a comprehension."""
    neighbours = [{"id": i, "infected": False} for i in range(100)]
    expr = '[n["id"] for n in neighbours if random() < 0.3]'
    first = _safe_eval(expr, StubAgent({}), neighbours, rng=rng_for(11))
    second = _safe_eval(expr, StubAgent({}), neighbours, rng=rng_for(11))
    assert first == second
    assert 0 < len(first) < 100  # sanity: some, but not all, selected


# ---- _evaluate_condition --------------------------------------------------


def test_condition_with_rng_returns_real_bool():
    agent = StubAgent({})
    assert _evaluate_condition("random() < 1.0", agent, rng=rng_for(1)) is True
    assert _evaluate_condition("random() < 0.0", agent, rng=rng_for(1)) is False


def test_condition_without_rng_rejects_helpers():
    with pytest.raises(ValueError):
        _evaluate_condition("random() < 0.5", StubAgent({}))


def test_condition_same_run_seed_same_outcomes():
    agent = StubAgent({})

    def outcomes(seed: int) -> list[bool]:
        rng = rng_for(seed)
        return [_evaluate_condition("random() < 0.5", agent, rng=rng) for _ in range(50)]

    assert outcomes(5) == outcomes(5)
    assert outcomes(5) != outcomes(6)


# ---- evaluate_expression (legacy path) ------------------------------------


def test_evaluate_expression_assigns_helper_value():
    agent = StubAgent({"count": 0})
    evaluate_expression('state["count"] = binomial(10, 1.0)', agent, [], rng=rng_for(1))
    assert agent.state["count"] == 10


def test_evaluate_expression_seeded_is_repeatable():
    first, second = StubAgent({"x": 0.0}), StubAgent({"x": 0.0})
    evaluate_expression('state["x"] = normal(0, 1, seed=4)', first, [], rng=rng_for(1))
    evaluate_expression('state["x"] = normal(0, 1, seed=4)', second, [], rng=rng_for(2))
    assert first.state["x"] == second.state["x"]

# Rule-step tests: distribution helpers inside conditions and then/else blocks.

def rng_for(seed: int) -> np.random.Generator:
    """Return a fresh central generator for the given run seed."""
    return np.random.default_rng(seed)


def make_agent(agent_id: str = "a1", **state) -> "AgentState":
    """Create an AgentState of type 'agent' with the given state."""
    return AgentState(agent_id=agent_id, agent_type_name="agent", state=dict(state))


def test_helper_in_condition_takes_then_branch():
    agent = make_agent(alert=False)
    steps = build_rule_steps(
        [
            {
                "condition": "random() < 1.0",
                "then": [{"field": "alert", "expression": "True"}],
                "else": [],
            }
        ],
        topology_names=[],
    )
    run_rule_steps(steps, agent, lambda *_a: [], rng=rng_for(1))
    assert agent.get("alert") is True


def test_helper_in_condition_takes_else_branch():
    agent = make_agent(alert=True)
    steps = build_rule_steps(
        [
            {
                "condition": "random() < 0.0",
                "then": [],
                "else": [{"field": "alert", "expression": "False"}],
            }
        ],
        topology_names=[],
    )
    run_rule_steps(steps, agent, lambda *_a: [], rng=rng_for(1))
    assert agent.get("alert") is False


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