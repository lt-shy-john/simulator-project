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

"""
Helper function in list comprehension
"""


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
	focal = FakeAgent('a', status='S', energy=10)
	neighbours = [
		FakeAgent('b', status='I', energy=60),
		FakeAgent('c', status='S', energy=40),
		FakeAgent('d', status='I', energy=50),
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
	expr = """[neighbor_count('state["status"] == "I"') for n in neighbours]"""
	# Helpers are bound to the focal agent's neighbours, so every iteration
	# sees the same count; n is not involved.
	assert evaluate(expr, focal, neighbours) == [2, 2, 2]


def test_helper_and_comprehension_variable_together(focal_and_neighbours):
	focal, neighbours = focal_and_neighbours
	expr = """[n['energy'] + neighbor_count('state["status"] == "I"') for n in neighbours]"""
	assert evaluate(expr, focal, neighbours) == [62, 42, 52]


def test_helper_and_comprehension_in_one_expression(focal_and_neighbours):
	focal, neighbours = focal_and_neighbours
	expr = (
		"""neighbor_sum('energy', 'state["status"] == "I"') """
		"""+ sum(n['energy'] for n in neighbours if n['status'] == 'S')"""
	)
	assert evaluate(expr, focal, neighbours) == 150  # (60 + 50) + 40


def test_filter_without_state_prefix_is_rejected(focal_and_neighbours):
	focal, neighbours = focal_and_neighbours
	expr = """[neighbor_count('status == "I"') for n in neighbours]"""
	with pytest.raises(ValueError):
		evaluate(expr, focal, neighbours)


# sandbox must not leak through the new nodes


@pytest.mark.parametrize(
	'expr',
	[
		'[n.__class__ for n in neighbours]',
		'[().__class__.__mro__ for n in neighbours]',
		"[__import__('os') for n in neighbours]",
	],
)
def test_comprehension_cannot_reach_dunders_or_imports(graph, expr):
	with pytest.raises(ValueError):
		_safe_eval(expr, graph.focal, graph.views)
