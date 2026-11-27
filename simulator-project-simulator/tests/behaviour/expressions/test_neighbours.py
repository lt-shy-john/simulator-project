import pytest
import logging
from types import SimpleNamespace

from behaviour.expressions import run_rule_steps, _safe_eval, _uses_neighbours
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
from runner.simulation import Simulation
from runner.state import AgentState

"""
Neighbour helpers
"""


def test_condition_can_use_neighbour_helper():
	agent = AgentState(agent_id='a1', agent_type_name='agent', state={'alert': False})
	neighbours = [
		AgentState(agent_id='n1', agent_type_name='agent', state={'status': 'I'}),
		AgentState(agent_id='n2', agent_type_name='agent', state={'status': 'S'}),
	]
	steps = build_rule_steps(
		[
			{
				'condition': """neighbor_count('state["status"] == "I"') > 0""",
				'then': [{'field': 'alert', 'expression': 'True'}],
				'else': [],
			}
		],
		topology_names=[],
	)

	run_rule_steps(steps, agent, lambda _t: neighbours)

	assert agent.get('alert') is True


@pytest.mark.parametrize(
	'expression, expected',
	[
		('neighbor_count(\'state["x"] > 1\') > 0', True),  # helper call
		("sum(n['e'] for n in neighbours)", True),  # `neighbours` name
		("state['neighbor_count'] + 1", False),  # substring only, no Call
		("state['energy'] - 0.5", False),
	],
)
def test_calls_neighbour_helper_detection(expression, expected):
	assert calls_neighbour_helper(expression) is expected


def test_neighbours_name_requires_topology_with_two_topologies():
	raw = [{'field': 'e', 'expression': "sum(n['e'] for n in neighbours)"}]

	build_rule_steps(raw, topology_names=['a'])  # one topology: fine
	with pytest.raises(ValueError):
		build_rule_steps(raw, topology_names=['a', 'b'])


THREE_LEVEL = "[o['status'] for n in neighbours for m in n['neighbours'] for o in m['neighbours']]"


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
	statuses = {'a': 'S', 'b': 'I', 'c': 'S', 'd': 'I', 'e': 'S'}
	agents = {k: SimpleNamespace(agent_id=k, state={'status': v}) for k, v in statuses.items()}
	adjacency = {'a': ['b', 'c'], 'b': ['a', 'd', 'e'], 'c': ['a']}

	def neighbours_of(aid):
		return [agents[i] for i in adjacency.get(aid, [])]

	return SimpleNamespace(
		focal=agents['a'],
		neighbours_of=neighbours_of,
		views=build_views_from_states(neighbours_of('a'), neighbours_of),
	)


# --- evaluation through _safe_eval ------------------------------------------


@pytest.mark.parametrize(
	'name, key',
	[
		('neighbors', 'neighbors'),
		('neighbours', 'neighbours'),
		('neighbors', 'neighbours'),
		('neighbours', 'neighbors'),
	],
)
def test_both_spellings_behave_identically(graph, name, key):
	"""Either spelling works as the name and as the nested key."""
	expr = f"[m['status'] for n in {name} for m in n['{key}']]"
	assert _safe_eval(expr, graph.focal, graph.views) == ['S', 'I', 'S', 'S']


def test_single_level_comprehension(graph):
	expr = "[n['status'] for n in neighbours]"
	assert _safe_eval(expr, graph.focal, graph.views) == ['I', 'S']


def test_two_hop_beyond_evaluates_by_default(graph):
	"""Soft limit only: nesting past one hop warns but still evaluates."""
	assert _safe_eval(THREE_LEVEL, graph.focal, graph.views) == ['I', 'S', 'I', 'S']


def test_two_hop_beyond_rejected_when_hard_cap_configured(graph):
	with pytest.raises(ComprehensionDepthError):
		_safe_eval(THREE_LEVEL, graph.focal, graph.views, sandbox=SandboxConfig(max_hops=1))


def test_comprehension_over_no_neighbours_is_empty(graph):
	assert _safe_eval("[n['status'] for n in neighbours]", graph.focal, []) == []
	assert _evaluate_condition('len([n for n in neighbours]) == 0', graph.focal, []) is True


def test_condition_neighbour_cap_from_config(graph):
	expr = 'len([n for n in neighbours]) > 0'
	with pytest.raises(NeighborSetTooLargeError):
		_evaluate_condition(
			expr,
			graph.focal,
			graph.neighbours_of('a'),
			sandbox=SandboxConfig(max_neighbours=1),  # 'a' has 2 neighbours
		)


def test_condition_hard_hop_cap(graph):
	expr = "len([o for n in neighbours for m in n['neighbours'] for o in m['neighbours']]) > 0"
	with pytest.raises(ComprehensionDepthError):
		_evaluate_condition(
			expr,
			graph.focal,
			graph.neighbours_of('a'),
			neighbours_of=graph.neighbours_of,
			sandbox=SandboxConfig(max_hops=1),
		)


# --- hop analysis ------------------------------------------------------------


@pytest.mark.parametrize('nb', ['neighbors', 'neighbours'])
@pytest.mark.parametrize(
	'template, hop',
	[
		('[n for n in {nb}]', 0),
		("[m for n in {nb} for m in n['{nb}']]", 1),
		("[[m for m in n['{nb}']] for n in {nb}]", 1),
		("max(len(n['{nb}']) for n in {nb})", 1),  # needs the _max_hop fix
		("[o for n in {nb} for m in n['{nb}'] for o in m['{nb}']]", 2),
		('[x for x in range(3)]', -1),
	],
)
def test_hop_analysis(template, hop, nb):
	assert analyse_expression(template.format(nb=nb)).max_hop == hop


# --- warn once ---------------------------------------------------------------


def _hop_warnings(caplog):
	return [r for r in caplog.records if 'hops beyond' in r.message]


def test_hop_warning_logged_once_per_expression(caplog):
	with caplog.at_level(logging.WARNING, logger='simulator'):
		first = check_comprehension_policy(THREE_LEVEL)
		second = check_comprehension_policy(THREE_LEVEL)
	assert len(_hop_warnings(caplog)) == 1
	assert first.warnings and second.warnings  # still available for the UI


def test_hop_warning_logged_again_for_a_different_expression(caplog):
	other = "[p['status'] for n in neighbours for m in n['neighbours'] for p in m['neighbours']]"
	with caplog.at_level(logging.WARNING, logger='simulator'):
		check_comprehension_policy(THREE_LEVEL)
		check_comprehension_policy(other)
	assert len(_hop_warnings(caplog)) == 2


# --- caps and config ---------------------------------------------------------


def test_neighbour_cap_uses_configured_value():
	sandbox = SandboxConfig(max_neighbours=3)
	check_neighbour_cap([{}, {}, {}], sandbox.max_neighbours)  # at the cap: fine
	with pytest.raises(NeighborSetTooLargeError):
		check_neighbour_cap([{}, {}, {}, {}], sandbox.max_neighbours, agent_id='a')


def test_sandbox_config_rejects_invalid_values():
	with pytest.raises(ValueError):
		SandboxConfig(max_neighbours=0)


def test_to_config_round_trips_sandbox_limits(base_config):
	"""A custom sandbox section survives from_config -> to_config."""
	base_config['sandbox'] = {'max_neighbours': 5000}
	out = Simulation.from_config(base_config).to_config()
	assert out['sandbox']['max_neighbours'] == 5000
	assert out['sandbox']['max_hops'] is None


def test_sandbox_cap_reaches_expression_evaluation(base_config):
	"""max_neighbours from the config must stop an oversized comprehension."""
	base_config['sandbox'] = {'max_neighbours': 1}
	base_config['behaviours'] = {
		'person': [
			{
				'expression': 'state["age"] += len([n for n in neighbours])',
				'topology_name': 'contact',
			}
		]
	}
	sim = Simulation.from_config(base_config)
	with pytest.raises(ValueError, match='capped at 1'):
		sim()


def test_one_hop_beyond_works_on_the_rule_path(base_config):
	"""n['neighbours'] must work through the rule path (plain dicts there
	would raise KeyError)."""
	base_config['behaviours'] = {
		'person': [
			{
				'field': 'age',
				'expression': ("state['age'] + len([m for n in neighbours for m in n['neighbours']])"),
				'topology_name': 'contact',
			}
		]
	}
	sim = Simulation.from_config(base_config)
	result = sim()
	assert result.stopped is True
	assert result.reason == 'max_steps'
	assert all(a.state['age'] >= 3 for a in sim.live_population.values())


# --- views -------------------------------------------------------------------


def test_views_expose_one_hop_beyond(graph):
	assert [v['status'] for v in graph.views] == ['I', 'S']
	assert [m['status'] for m in graph.views[0]['neighbours']] == ['S', 'I', 'S']


def test_deeper_hop_is_capped(graph):
	views = build_views_from_states(graph.neighbours_of('a'), graph.neighbours_of, max_neighbors=2)
	with pytest.raises(NeighborSetTooLargeError):
		views[0]['neighbours']  # b has 3 neighbours


# --- conditions --------------------------------------------------------------


@pytest.mark.parametrize('name', ['neighbours', 'neighbors'])
def test_condition_reaches_one_hop_beyond(graph, name):
	expr = f"len([m for n in {name} for m in n['{name}'] if m['status'] == 'I']) >= 1"
	assert (
		_evaluate_condition(
			expr,
			graph.focal,
			graph.neighbours_of('a'),
			neighbours_of=graph.neighbours_of,
		)
		is True
	)


def test_uses_neighbours_accepts_both_spellings():
	assert _uses_neighbours('len([n for n in neighbors]) > 0')
	assert _uses_neighbours('len([n for n in neighbours]) > 0')
