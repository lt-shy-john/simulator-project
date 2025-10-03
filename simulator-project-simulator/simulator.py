import sys

from runner.simulation import Simulation

try:
    T = int(sys.argv[2])
except IndexError:
    print("No simulation time specified.")
    T = 10

if sys.argv[-1] == 'run':
    simulation = Simulation(10, T)
    simulation()