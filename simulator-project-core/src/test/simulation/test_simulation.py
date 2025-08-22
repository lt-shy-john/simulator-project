from ...models import Simulation
from ...util.customLogger import *

from django.test import TestCase

class TestSimulation(TestCase):
    def setUp(self) -> None:
        N = 50
        T = 10

        self.simulation = Simulation(N, T, gen_logging('', None))

    def normal_run(self):
        self.simulation.run()