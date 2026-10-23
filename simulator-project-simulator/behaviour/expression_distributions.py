"""RNG-backed probability-distribution helpers for the expression sandbox.

Behaviour authors can call these inside any sandboxed expression, including
``then``/``else`` blocks and comprehensions::

    random()                    -> float in [0, 1)
    normal(mean, std)           -> float
    binomial(n, p)              -> int
    poisson(lam)                -> int

Each helper also accepts an optional ``seed`` (keyword or as the last
positional argument), e.g. ``normal(0, 1, seed=7)``.

Determinism guarantees (two distinct guarantees)
------------------------------------------------
1. **Unseeded calls** draw from the simulation's shared RNG stream. Their
   values are reproducible *across full runs* that use the same top-level run
   seed and make the same sequence of calls. A single call has no standalone
   guarantee: its value depends on how many draws came before it.
2. **Seeded calls** (``seed`` is not ``None``) build a fresh, private
   generator from ``seed`` on *every invocation*. The same arguments plus the
   same seed return the same value every time, regardless of the run seed or
   call order. Seeded calls never consume from, or advance, the shared
   stream, so adding a seeded call does not perturb unseeded draws.

Consequence: ``random(seed=1)`` inside a comprehension returns the *same*
value for every element. Use unseeded calls when each agent should draw
independently.

Extending the helper set
------------------------
The set is a closed, explicit registry. Nothing is passed through to
``random`` / ``numpy.random``. To add a helper (e.g. ``exponential``):

1. Write a draw function ``(rng: Generator, <params>) -> int | float`` that
   validates its arguments and returns a native Python number (not a NumPy
   scalar).
2. Register it with ``@distribution("exponential")``.
3. Add tests: shape (statistical sanity), unseeded determinism, seeded
   determinism, and argument validation.
4. Add the helper to the documentation table of available helpers.

The ``seed`` handling is added automatically for every registered helper.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from numpy.random import Generator

DrawFn = Callable[..., "int | float"]


@dataclass(frozen=True)
class _Spec:
    """A registered distribution: its draw function and positional arity."""

    draw: DrawFn
    arity: int  # number of distribution parameters, excluding rng and seed


_REGISTRY: dict[str, _Spec] = {}


def distribution(name: str) -> Callable[[DrawFn], DrawFn]:
    """Register a draw function as a sandbox helper called ``name``.

    The decorated function must take the ``Generator`` as its first argument,
    followed by the distribution parameters.

    Args:
        name: The name exposed to expressions.

    Returns:
        The decorator; the draw function is returned unchanged.

    Raises:
        ValueError: If ``name`` is already registered.
    """

    def decorator(fn: DrawFn) -> DrawFn:
        if name in _REGISTRY:
            raise ValueError(f"Distribution {name!r} is already registered")
        arity = len(inspect.signature(fn).parameters) - 1
        _REGISTRY[name] = _Spec(draw=fn, arity=arity)
        return fn

    return decorator


def _is_int(value: Any) -> bool:
    """Return True for real integers (bool is rejected)."""
    return isinstance(value, (int, np.integer)) and not isinstance(value, bool)


def _check_seed(seed: Any) -> None:
    """Validate a per-call seed.

    Raises:
        TypeError: If ``seed`` is neither ``None`` nor an integer.
    """
    if seed is not None and not _is_int(seed):
        raise TypeError(f"seed must be an int or None, got {type(seed).__name__}")


# --------------------------------------------------------------------------
# Registered distributions
# --------------------------------------------------------------------------


@distribution("random")
def _random(rng: Generator) -> float:
    """Uniform float in [0, 1)."""
    return float(rng.random())


@distribution("normal")
def _normal(rng: Generator, mean: float, std: float) -> float:
    """Normal (Gaussian) draw with the given mean and standard deviation."""
    if not std >= 0:  # also rejects NaN
        raise ValueError(f"normal(): std must be >= 0, got {std!r}")
    return float(rng.normal(mean, std))


@distribution("binomial")
def _binomial(rng: Generator, n: int, p: float) -> int:
    """Number of successes in ``n`` independent trials of probability ``p``."""
    if not _is_int(n) or n < 0:
        raise ValueError(f"binomial(): n must be an integer >= 0, got {n!r}")
    if not 0 <= p <= 1:  # also rejects NaN
        raise ValueError(f"binomial(): p must be in [0, 1], got {p!r}")
    return int(rng.binomial(n, p))


@distribution("poisson")
def _poisson(rng: Generator, lam: float) -> int:
    """Poisson draw with rate ``lam``."""
    if not lam >= 0:  # also rejects NaN
        raise ValueError(f"poisson(): lam must be >= 0, got {lam!r}")
    return int(rng.poisson(lam))


# --------------------------------------------------------------------------
# Binding to a simulation RNG
# --------------------------------------------------------------------------


def _bind(name: str, spec: _Spec, rng: Generator) -> Callable[..., int | float]:
    """Create the sandbox-facing helper for one distribution.

    Args:
        name: Helper name (used in error messages).
        spec: The registered draw function and its arity.
        rng: The simulation's shared generator, used for unseeded calls.

    Returns:
        A callable accepting the distribution parameters plus optional ``seed``.
    """

    def helper(*args: Any, seed: int | None = None) -> int | float:
        """Draw a value; ``seed`` (optional) makes the call self-contained."""
        if len(args) == spec.arity + 1:
            if seed is not None:
                raise TypeError(f"{name}() got multiple values for 'seed'")
            *args, seed = args
        elif len(args) != spec.arity:
            raise TypeError(
                f"{name}() takes {spec.arity} positional argument(s) "
                f"plus optional seed, got {len(args)}"
            )
        _check_seed(seed)
        source = rng if seed is None else np.random.default_rng(seed)
        return spec.draw(source, *args)

    helper.__name__ = name
    return helper


def build_distribution_functions(rng: Generator) -> dict[str, Callable[..., int | float]]:
    """Build the helper dict to merge into the sandbox's ``functions``.

    Args:
        rng: The simulation's central generator (S-11). Unseeded helper
            calls draw from it; seeded calls never touch it.

    Returns:
        Mapping of helper name to callable, for every registered distribution.
    """
    return {name: _bind(name, spec, rng) for name, spec in _REGISTRY.items()}


def available_distributions() -> tuple[str, ...]:
    """Return the names of all registered helpers (for docs and error text)."""
    return tuple(_REGISTRY)