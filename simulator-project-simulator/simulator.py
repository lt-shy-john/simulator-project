import sys
import datetime

from runner.simulation import Simulation
import runner.customLogger as logger

filename = 'Test-' + datetime.datetime.now().strftime("%Y%m%d")
root_logger = logger.gen_logging(filename, None)

try:
    N = int(sys.argv[1])
except IndexError:
    print("No simulation agent number specified.")
    N = 3
try:
    T = int(sys.argv[2])
except IndexError:
    print("No simulation agent time specified.")
    T = 10

if sys.argv[-1] == 'run':
    simulation = Simulation(N, T, root_logger, name=filename)
    simulation()