import sys
import inspect
import logging

import util.util as util
from runner.simulation import Simulation

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
    current_run = Simulation(settings["N"], settings["T"], **{k: v for k, v in settings.items() if k not in ("N", "T")})
    current_run()

def do_setting():
    pass

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