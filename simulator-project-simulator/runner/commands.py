import sys
import inspect
import logging

from runner.simulation import Simulation

logger = logging.getLogger('simulator')

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

def do_run(N, T, **kwargs):
    current_run = Simulation(N, T)
    current_run()

def do_setting():
    pass

def do_summary():
    pass

def do_look():
    pass