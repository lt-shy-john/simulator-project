"""
registry.py — Behaviour module registry (S-05).

Scope:
  - register_behaviour: decorator for registering a BehaviourModule class
    under a name, so it can be looked up from config.
  - get_behaviour: lookup a registered class by name.
  - list_registered: for error messages and introspection.

Design notes:
  - Decorator pattern (Pattern A from ticket discussion), not a central
    "all modules" file. A module class registers itself:

        @register_behaviour("SIRInfection")
        class SIRInfection(BehaviourModule):
            ...

  - The decorator only runs when Python actually imports the file it's
    in. A module can have a perfectly correct @register_behaviour
    decorator and still never register if nothing ever imports its file.
    Whatever __init__.py sits above a topic-library folder (e.g.
    behaviour_library/epidemic/__init__.py) MUST import every module
    file in that folder, even if nothing in __init__.py directly uses
    them, purely to trigger the decorators. This is a common gotcha —
    if a module doesn't show up in the registry, check imports first,
    not the decorator itself.

  - Duplicate registration (same name registered twice) raises rather
    than silently overwriting, since a silent overwrite could mean a
    researcher's custom module quietly shadows a built-in one (or
    vice versa) with no warning.

Not in scope here:
  - Concrete module implementations — those live in topic-library
    folders and import this module to self-register.
  - How topic-library folders get imported at simulation startup —
    that's part of the run-handoff / initialisation story, not this file.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from behaviour.base import BehaviourModule

T = TypeVar("T", bound=BehaviourModule)


# Registry is a module-level dict — one registry shared across the whole
# process. name -> BehaviourModule class (not instance).
_registry: dict[str, type[BehaviourModule]] = {}


def register_behaviour(name: str) -> Callable[[T], T]:
    """Decorator that registers a BehaviourModule class under `name`.

    Usage:
        @register_behaviour("SIRInfection")
        class SIRInfection(BehaviourModule):
            ...

    The decorated class is returned unchanged — this only has the side
    effect of adding it to the registry.

    Args:
        name: the name this module will be looked up by from config

    Returns:
        a decorator function

    Raises:
        ValueError: if `name` is already registered to a different class
            (re-registering the exact same class under the same name is
            harmless and allowed, to tolerate module re-import during
            testing or reload)
    """
    def decorator(cls: T) -> T:
        if name in _registry and _registry[name] is not cls:
            raise ValueError(
                f"Behaviour module name '{name}' is already registered to "
                f"'{_registry[name].__name__}'. Cannot register '{cls.__name__}' "
                f"under the same name. Choose a different name, or check for "
                f"a duplicate registration."
            )
        _registry[name] = cls
        return cls

    return decorator


def get_behaviour(name: str) -> type[BehaviourModule]:
    """Look up a registered BehaviourModule class by name.

    Args:
        name: the registered module name (as used in config)

    Returns:
        the BehaviourModule class (not an instance — caller constructs
        it with whatever params come from config)

    Raises:
        KeyError: if `name` is not registered. Message includes the list
            of currently registered names, which is often the fastest way
            to spot a typo or a missing import (see module docstring note
            about __init__.py needing to import every module file).
    """
    if name not in _registry:
        raise KeyError(
            f"Unknown behaviour module '{name}'. "
            f"Registered modules: {sorted(_registry.keys())}. "
            f"If you expected '{name}' to be registered, check that the "
            f"file defining it is actually imported somewhere at startup."
        )
    return _registry[name]


def list_registered() -> list[str]:
    """Return a sorted list of all currently registered behaviour module names."""
    return sorted(_registry.keys())


def _clear_registry_for_testing() -> None:
    """Clear the registry. Intended for use in test teardown only, to
    avoid state leaking between tests that register modules under the
    same name. Not part of the public API."""
    _registry.clear()