import os
import sys
import datetime

import runner.commands as commands
from runner.simulation import Simulation
import runner.customLogger as logger

filename = 'Test-' + datetime.datetime.now().strftime("%Y%m%d")
root_logger = logger.gen_logging(filename, os.path.splitext(os.path.basename(__file__))[0] ,None)

# Initial settings and express mode
if len(sys.argv) == 3:
    try:
        N = int(sys.argv[1])
    except IndexError:
        root_logger.info("No simulation agent number specified.")
        commands.set_N()
    try:
        T = int(sys.argv[2])
    except IndexError:
        root_logger.info("No simulation agent time specified.")
        commands.set_T()

    if sys.argv[-1] == 'run':
        simulation = Simulation(N, T, root_logger, name=filename)
        simulation()
else:
    if sys.argv[-1] == 'help':
        commands.usage()
        commands.do_help()
        sys.exit(0)
    if len(sys.argv) == 2:
        commands.settings['N'] = int(sys.argv[1])
        commands.set_T()
    else:
        commands.basic_settings()


# Normal interface

cmd = ""

root_logger.info('Welcome to the Agent Based Simulator!')
root_logger.info('Please enter your command below: ')
while cmd.lower() not in ["exit", "quit"]:
    cmd = input('> ')
    handler = getattr(commands, f"do_{cmd}", None)
    root_logger.debug(f"Looking for: do_{cmd}, found: {handler}")
    if handler is not None:
        handler()
    else:
        root_logger.warning(f"Unknown command: '{cmd}'")