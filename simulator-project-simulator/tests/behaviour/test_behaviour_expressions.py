import pytest
import uuid
import random
import logging
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