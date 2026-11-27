import pytest
import numpy as np

from behaviour import expression_distributions as dist  # for monkey patching
from behaviour.expression_distributions import (
	available_distributions,
	build_distribution_functions,
	distribution,
)

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
		out += [
			h['random'](),
			h['normal'](0, 1),
			h['binomial'](10, 0.5),
			h['poisson'](3),
		]
	return out


# ---- registry -------------------------------------------------------------


def test_helper_set_is_fixed():
	assert set(available_distributions()) == {'random', 'normal', 'binomial', 'poisson'}
	assert set(make_helpers()) == set(available_distributions())


def test_extension_via_registry(monkeypatch):
	monkeypatch.setattr(dist, '_REGISTRY', dict(dist._REGISTRY))

	@distribution('exponential')
	def _exponential(rng, scale):
		return float(rng.exponential(scale))

	h = make_helpers()
	assert h['exponential'](2.0, seed=1) == h['exponential'](2.0, seed=1)


# ---- determinism ----------------------------------------------------------


def test_unseeded_deterministic_across_full_runs():
	assert simulate_run(123) == simulate_run(123)


def test_unseeded_differs_for_different_run_seed():
	assert simulate_run(123) != simulate_run(124)


@pytest.mark.parametrize(
	'name,args',
	[('random', ()), ('normal', (0, 1)), ('binomial', (10, 0.5)), ('poisson', (3,))],
)
def test_seeded_deterministic_per_invocation(name, args):
	h = make_helpers()
	first = h[name](*args, seed=7)
	assert all(h[name](*args, seed=7) == first for _ in range(20))
	assert h[name](*args, 7) == first  # positional seed form


def test_seeded_independent_of_run_seed():
	assert make_helpers(1)['normal'](0, 1, seed=7) == make_helpers(2)['normal'](0, 1, seed=7)


def test_seeded_calls_do_not_advance_shared_stream():
	plain, mixed = make_helpers(5), make_helpers(5)
	expected = [plain['random']() for _ in range(10)]
	actual = []
	for _ in range(10):
		mixed['random'](seed=99)
		actual.append(mixed['random']())
	assert actual == expected


def test_different_seeds_give_different_values():
	h = make_helpers()
	assert h['random'](seed=1) != h['random'](seed=2)


# ---- distribution shape (fixed seed, so these cannot flake) ----------------


def test_random_shape():
	h = make_helpers(2024)
	xs = np.array([h['random']() for _ in range(N_SAMPLES)])
	assert xs.min() >= 0.0 and xs.max() < 1.0
	assert xs.mean() == pytest.approx(0.5, abs=0.02)


def test_normal_shape():
	h = make_helpers(2024)
	xs = np.array([h['normal'](10, 2) for _ in range(N_SAMPLES)])
	assert xs.mean() == pytest.approx(10, abs=0.1)
	assert xs.std() == pytest.approx(2, abs=0.1)


def test_binomial_shape():
	h = make_helpers(2024)
	xs = np.array([h['binomial'](20, 0.3) for _ in range(N_SAMPLES)])
	assert xs.min() >= 0 and xs.max() <= 20
	assert xs.mean() == pytest.approx(6.0, abs=0.1)
	assert xs.var() == pytest.approx(4.2, abs=0.3)


def test_poisson_shape():
	h = make_helpers(2024)
	xs = np.array([h['poisson'](4) for _ in range(N_SAMPLES)])
	assert xs.min() >= 0
	assert xs.mean() == pytest.approx(4.0, abs=0.1)
	assert xs.var() == pytest.approx(4.0, abs=0.3)


def test_return_types_are_native_python():
	h = make_helpers()
	assert type(h['random']()) is float
	assert type(h['normal'](0, 1)) is float
	assert type(h['binomial'](5, 0.5)) is int
	assert type(h['poisson'](2)) is int


# ---- validation -----------------------------------------------------------


@pytest.mark.parametrize(
	'name,args',
	[
		('normal', (0, -1)),
		('normal', (0, float('nan'))),
		('binomial', (-1, 0.5)),
		('binomial', (5.5, 0.5)),
		('binomial', (5, 1.5)),
		('binomial', (5, float('nan'))),
		('poisson', (-0.1,)),
	],
)
def test_invalid_arguments_raise_value_error(name, args):
	with pytest.raises(ValueError):
		make_helpers()[name](*args)


@pytest.mark.parametrize('bad_seed', ['abc', 1.5, True])
def test_invalid_seed_raises_type_error(bad_seed):
	with pytest.raises(TypeError):
		make_helpers()['random'](seed=bad_seed)


def test_wrong_arity_raises_type_error():
	with pytest.raises(TypeError):
		make_helpers()['normal'](0)
	with pytest.raises(TypeError):
		make_helpers()['normal'](0, 1, 2, 3)
	with pytest.raises(TypeError):
		make_helpers()['normal'](0, 1, 2, seed=3)  # seed given twice
