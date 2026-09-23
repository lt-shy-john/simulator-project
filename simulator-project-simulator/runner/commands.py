import sys
import inspect
import logging

from pydantic import ValidationError

import util.util as util
from runner.simulation import Simulation
from runner.simulationConfig import SimulationConfig
from agents.models import AttributeType

logger = logging.getLogger('simulator')

settings = {'name': ''}

def do_exit():
    """Exit the program."""
    logger.info('Bye!')
    sys.exit()

def do_quit():
    """Alias for exit."""
    do_exit()

def do_help():
    """Show all available commands and their descriptions."""
    current_module = sys.modules[__name__]
    logger.info('\nAvailable commands: ')

    for name, fn in inspect.getmembers(current_module, inspect.isfunction):
        if name.startswith("do_"):
            cmd_name = name[3:]
            description = (fn.__doc__ or "No description available.").strip().splitlines()[0]
            logger.info(f"  {cmd_name:<15} {description}")
    logger.info('')  # Extra new line

def do_run():
    """Run the simulation using the config built by 'setting'."""

    if "config" not in settings:
        logger.warning("No simulation configured yet — run 'setting' first.")
        return
    current_run = Simulation.from_config(settings["config"])
    current_run()
    
def default_config(n: int, t: int) -> dict:
    """Build a minimal, hardcoded config for express-mode smoke tests
    (`python3 simulator.py N T run`) — N and T are the only inputs a user
    provides at that point, so this fills in the rest with fixed
    placeholder choices: one agent type with a single int attribute
    starting at 0, incremented by 1 each step, on an all_pairs topology,
    running to completion in all_at_once/frozen order.

    This is deliberately not configurable — it exists to let 'N T run'
    keep working as a quick sanity check, not to express real simulation
    intent. Use 'setting' for anything that needs to mean something.
    """
    return {
        "seed": None,
        "agent_types": [
            {
                "name": "agent",
                "count": n,
                "generation_mode": "heterogeneous",
                "attributes": [
                    {
                        "name": "step_count",
                        "type": "int",
                        "population_method": "distribution",
                        "distribution": {"kind": "fixed", "value": 0},
                    }
                ],
            }
        ],
        "topologies": {"contact": {"mode": "all_pairs", "agent_types": ["agent"]}},
        "behaviours": {
            "agent": [{"expression": 'state["step_count"] = 1', "topology_name": "contact"}]
        },
        "scheduler": {"order": "all_at_once", "read_mode": "frozen"},
        "stopping": {"max_steps": t, "conditions": [], "combinator": "OR"},
    }

def do_run_default():
    """Run the express-mode default config (see default_config) using
    the currently set N and T. Does not require 'setting' to have been
    run — this is the express-mode `N T run` path's entry point."""
    if "N" not in settings or "T" not in settings:
        logger.warning("N and T must be set before running the default config.")
        return
    logger.info(
        f"Running default config: {settings['N']} agents, "
        f"{settings['T']} steps. Run 'setting' instead to configure a "
        f"real simulation."
    )
    current_run = Simulation.from_config(default_config(settings["N"], settings["T"]))
    current_run()

def do_setting():
    """Interactively build a full simulation config
    (agent type, attributes, topology, behaviour, scheduler, stopping)
    and validate it against SimulationConfig.

    Scope for this MVP flow — each is a deliberate simplification, not
    a schema limitation (the underlying config supports more):
      - seed is a single optional int prompt (S-11); there's no prompt
        for config.params (global behaviour-module parameters) — those
        aren't reachable through this flow yet, same reasoning as
        module-based behaviours below
      - exactly one agent type, always generation_mode="heterogeneous"
        (every attribute is distribution-driven; homogeneous/fixed-value
        agent types aren't reachable through this prompt flow yet)
      - exactly one topology; behaviours are one or more expressions
        against that single topology (not registered modules — module
        params aren't prompt-able generically)
      - no extra stopping conditions beyond max_steps (T, already
        collected at startup)
    If settings["config"] already exists from a previous 'setting' run,
    you're offered the option to reuse its agent type name and
    attributes as-is instead of re-entering them — handy for iterating
    on topology/behaviour/scheduler without retyping the agent setup
    each time. Everything else (topology, behaviour, scheduler) is
    always re-prompted fresh.
    On a validation error, the whole flow is discarded — run 'setting'
    again from scratch rather than being re-prompted just for the
    offending field.
    """
    if "N" not in settings:
        set_N()
    if "T" not in settings:
        set_T()

    logger.info(
        "Optional: set a seed for reproducible runs (same seed + config "
        "-> identical results). Leave blank for an unseeded, "
        "non-reproducible run."
    )
    seed = util.prompt_optional_int("Seed [blank for none]: ")

    agent_type_name, attributes = _prompt_agent_type()

    topology_name, topology = _prompt_topology(agent_type_name)
    behaviour_entries = _prompt_behaviour(topology_name)
    scheduler = _prompt_scheduler()

    config = {
        "seed": seed,
        "agent_types": [
            {
                "name": agent_type_name,
                "count": settings["N"],
                "generation_mode": "heterogeneous",
                "attributes": attributes,
            }
        ],
        "topologies": {topology_name: topology},
        "behaviours": {agent_type_name: behaviour_entries},
        "scheduler": scheduler,
        "stopping": {"max_steps": settings["T"], "conditions": [], "combinator": "OR"},
    }

    try:
        SimulationConfig.model_validate(config)
    except ValidationError as e:
        logger.warning(f"Configuration is invalid — nothing saved. Details:\n{e}")
        return

    settings["config"] = config
    logger.info("Configuration saved. Run 'run' to start the simulation.")

def _prompt_agent_type() -> tuple[str, list[dict]]:
    """Return (agent_type_name, attributes) for the config being built.

    If settings["config"] already has an agent type from a previous
    'setting' run, offers to reuse its name and attributes as-is rather
    than re-prompting for them. Declining, or no existing config, falls
    through to the normal from-scratch prompt.
    """
    existing_config = settings.get("config")
    if existing_config is not None:
        existing_agent_type = existing_config["agent_types"][0]
        if util.prompt_yes_no(
            f"Reuse existing agent type '{existing_agent_type['name']}' "
            f"and its {len(existing_agent_type['attributes'])} attribute(s)? (y/n): "
        ):
            return existing_agent_type["name"], existing_agent_type["attributes"]

    agent_type_name = input("Agent type name [agent]: ").strip() or "agent"

    attributes = []
    logger.info(f"Now define attributes for '{agent_type_name}'.")
    while True:
        attributes.append(_prompt_attribute())
        if not util.prompt_yes_no("Add another attribute? (y/n): "):
            break

    return agent_type_name, attributes

def _prompt_attribute() -> dict:
    """Prompt for one AttributeDefinition-shaped dict: name, type, and a
    matching distribution. Always population_method='distribution', to
    match this flow's heterogeneous-only scope (see do_setting)."""
    name = input("  Attribute name: ").strip()
    type_choice = util.prompt_choice(
        f"  Type ({'/'.join(t.value for t in AttributeType)}): ",
        [t.value for t in AttributeType],
    )

    if type_choice in (AttributeType.INT.value, AttributeType.FLOAT.value):
        if util.prompt_yes_no("  Fixed value (not a range)? (y/n): "):
            value = (
                util.prompt_int("  Value: ") if type_choice == AttributeType.INT.value
                else util.prompt_float("  Value: ")
            )
            distribution = {"kind": "fixed", "value": value}
        else:
            prompt_fn = util.prompt_int if type_choice == AttributeType.INT.value else util.prompt_float
            low = prompt_fn("  Low: ")
            high = prompt_fn("  High: ")
            distribution = {"kind": "uniform", "low": low, "high": high}

    elif type_choice == AttributeType.BOOL.value:
        value = util.prompt_yes_no("  Fixed value — true? (y/n): ")
        distribution = {"kind": "fixed", "value": value}

    else:  # categorical
        raw = input("  Categories (comma-separated, equal weight): ").strip()
        categories = [c.strip() for c in raw.split(",") if c.strip()]
        distribution = {"kind": "categorical", "weights": {c: 1.0 for c in categories}}

    return {
        "name": name,
        "type": type_choice,
        "population_method": "distribution",
        "distribution": distribution,
    }

def _prompt_topology(agent_type_name: str) -> tuple[str, dict]:
    """Prompt for a single topology. Returns (name, config-dict)."""
    mode = util.prompt_choice(
        "Topology mode (all_pairs/random_sample/network): ",
        ["all_pairs", "random_sample", "network"],
    )
    name = input("Topology name [contact]: ").strip() or "contact"

    if mode == "all_pairs":
        return name, {"mode": "all_pairs", "agent_types": [agent_type_name]}

    if mode == "random_sample":
        k = util.prompt_int("  k (neighbours per agent): ")
        return name, {"mode": "random_sample", "k": k, "agent_types": [agent_type_name]}

    # network — MVP only offers erdos_renyi, matching N already collected
    p = util.prompt_float("  Edge probability p (0.0-1.0): ")
    return name, {
        "mode": "network",
        "agent_types": [agent_type_name],
        "graph": {"type": "erdos_renyi", "n": settings["N"], "p": p},
    }

def _prompt_behaviour(topology_name: str) -> list[dict]:
    """Prompt for one or more expression-based behaviour entries, applied
    to each agent, in the order entered, every step. Module-based
    behaviours aren't offered here — a registered module's constructor
    params vary per module, so there's no generic prompt for them."""
    logger.info(
        "Enter a Python expression to run on each agent each step, "
        "e.g. state['age'] = 1"
    )
    behaviours = []
    while True:
        expression = input("  Expression: ").strip()
        behaviours.append({"expression": expression, "topology_name": topology_name})
        if not util.prompt_yes_no("Add another expression? (y/n): "):
            break
    return behaviours

def _prompt_scheduler() -> dict:
    order = util.prompt_choice(
        "Scheduling order (all_at_once/random/priority) [all_at_once]: ",
        ["all_at_once", "random", "priority"],
    ) if input("Customise scheduling? (y/n): ").strip().lower() in ("y", "yes") else "all_at_once"

    scheduler = {"order": order, "read_mode": "frozen"}
    if order == "priority":
        scheduler["priority_attribute"] = input("  Priority attribute name: ").strip()
    return scheduler

def do_summary():
    """Show all available settings and their values."""
    logger.info(settings)

def do_look():
    pass

def usage():
    logger.info('python3 simulation.py [N] [T] ... [-f (filename)] [-verbose | --v <log_level>] [run]')

def basic_settings():
    """If number of agents and simulation time not defined, then ask user to enter it."""
    logger.info('No simulation settings provided.')
    set_N()
    set_T()

def set_N():
    logger.info('Please enter number of agents: ')
    settings["N"] = util.prompt_int()

def set_T():
    logger.info('Please enter simulation time (steps): ')
    settings["T"] = util.prompt_int()