import pytest
import numpy as np
import uuid
import random
import logging
import copy
from simpleeval import EvalWithCompoundTypes
from typing import Any
from types import SimpleNamespace

from behaviour.expressions import (
	evaluate_expression,
	run_rule_steps,
	_safe_eval,
	_uses_neighbours,
)
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

N_SAMPLES = 20_000


def make_helpers(run_seed: int = 42) -> dict:
	"""Build helpers bound to a fresh RNG for the given run seed."""
	return build_distribution_functions(np.random.default_rng(run_seed))


def make_evaluator(names: dict | None = None, run_seed: int = 42) -> EvalWithCompoundTypes:
	"""Sandbox evaluator with the distribution helpers installed."""
	return EvalWithCompoundTypes(names=names or {}, functions=make_helpers(run_seed))


def test_helpers_usable_in_ternary():
	ev = make_evaluator()
	assert ev.eval('1 if random(seed=3) < 2 else 0') == 1


def test_helpers_usable_in_comprehension_unseeded_are_independent():
	ev = make_evaluator({'neighbours': list(range(50))})
	draws = ev.eval('[random() for n in neighbours]')
	assert len(set(draws)) == 50


def test_seeded_in_comprehension_repeats_same_value():
	ev = make_evaluator({'neighbours': list(range(10))})
	draws = ev.eval('[random(seed=5) for n in neighbours]')
	assert len(set(draws)) == 1


def test_comprehension_infection_pattern_is_run_deterministic():
	"""The same run seed yields the same infected set from a comprehension."""
	expr = '[n for n in neighbours if random() < 0.3]'
	names = {'neighbours': list(range(200))}
	first = make_evaluator(names, 9).eval(expr)
	second = make_evaluator(names, 9).eval(expr)
	assert first == second
	assert 0 < len(first) < 200


def test_unknown_helper_is_not_available():
	from simpleeval import FunctionNotDefined

	with pytest.raises(FunctionNotDefined):
		make_evaluator().eval('exponential(1.0)')


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
	value = _safe_eval('random()', StubAgent({}), [], rng=rng_for(1))
	assert isinstance(value, float) and 0.0 <= value < 1.0


def test_safe_eval_same_run_seed_same_draws():
	expr = '[random(), normal(0, 1), binomial(10, 0.5), poisson(3)]'
	first = _safe_eval(expr, StubAgent({}), [], rng=rng_for(7))
	second = _safe_eval(expr, StubAgent({}), [], rng=rng_for(7))
	assert first == second


def test_safe_eval_without_rng_rejects_helpers():
	with pytest.raises(ValueError):
		_safe_eval('random()', StubAgent({}), [])


def test_safe_eval_without_rng_rejects_seeded_helpers_too():
	with pytest.raises(ValueError):
		_safe_eval('random(seed=1)', StubAgent({}), [])


def test_safe_eval_seeded_call_leaves_shared_stream_untouched():
	plain, mixed = rng_for(3), rng_for(3)
	expected = _safe_eval('random()', StubAgent({}), [], rng=plain)
	_safe_eval('random(seed=99)', StubAgent({}), [], rng=mixed)
	actual = _safe_eval('random()', StubAgent({}), [], rng=mixed)
	assert actual == expected


def test_safe_eval_comprehension_over_neighbours_is_run_deterministic():
	"""The same run seed selects the same neighbours from a comprehension."""
	neighbours = [{'id': i, 'infected': False} for i in range(100)]
	expr = '[n["id"] for n in neighbours if random() < 0.3]'
	first = _safe_eval(expr, StubAgent({}), neighbours, rng=rng_for(11))
	second = _safe_eval(expr, StubAgent({}), neighbours, rng=rng_for(11))
	assert first == second
	assert 0 < len(first) < 100  # sanity: some, but not all, selected


# ---- _evaluate_condition --------------------------------------------------


def test_condition_with_rng_returns_real_bool():
	agent = StubAgent({})
	assert _evaluate_condition('random() < 1.0', agent, rng=rng_for(1)) is True
	assert _evaluate_condition('random() < 0.0', agent, rng=rng_for(1)) is False


def test_condition_without_rng_rejects_helpers():
	with pytest.raises(ValueError):
		_evaluate_condition('random() < 0.5', StubAgent({}))


def test_condition_same_run_seed_same_outcomes():
	agent = StubAgent({})

	def outcomes(seed: int) -> list[bool]:
		rng = rng_for(seed)
		return [_evaluate_condition('random() < 0.5', agent, rng=rng) for _ in range(50)]

	assert outcomes(5) == outcomes(5)
	assert outcomes(5) != outcomes(6)


# ---- evaluate_expression (legacy path) ------------------------------------


def test_evaluate_expression_assigns_helper_value():
	agent = StubAgent({'count': 0})
	evaluate_expression('state["count"] = binomial(10, 1.0)', agent, [], rng=rng_for(1))
	assert agent.state['count'] == 10


def test_evaluate_expression_seeded_is_repeatable():
	first, second = StubAgent({'x': 0.0}), StubAgent({'x': 0.0})
	evaluate_expression('state["x"] = normal(0, 1, seed=4)', first, [], rng=rng_for(1))
	evaluate_expression('state["x"] = normal(0, 1, seed=4)', second, [], rng=rng_for(2))
	assert first.state['x'] == second.state['x']


# Rule-step tests: distribution helpers inside conditions and then/else blocks.


def rng_for(seed: int) -> np.random.Generator:
	"""Return a fresh central generator for the given run seed."""
	return np.random.default_rng(seed)


def make_agent(agent_id: str = 'a1', **state) -> 'AgentState':
	"""Create an AgentState of type 'agent' with the given state."""
	return AgentState(agent_id=agent_id, agent_type_name='agent', state=dict(state))


def test_helper_in_condition_takes_then_branch():
	agent = make_agent(alert=False)
	steps = build_rule_steps(
		[
			{
				'condition': 'random() < 1.0',
				'then': [{'field': 'alert', 'expression': 'True'}],
				'else': [],
			}
		],
		topology_names=[],
	)
	run_rule_steps(steps, agent, lambda *_a: [], rng=rng_for(1))
	assert agent.get('alert') is True


def test_helper_in_condition_takes_else_branch():
	agent = make_agent(alert=True)
	steps = build_rule_steps(
		[
			{
				'condition': 'random() < 0.0',
				'then': [],
				'else': [{'field': 'alert', 'expression': 'False'}],
			}
		],
		topology_names=[],
	)
	run_rule_steps(steps, agent, lambda *_a: [], rng=rng_for(1))
	assert agent.get('alert') is False
