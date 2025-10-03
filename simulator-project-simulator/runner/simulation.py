import random
import time
import datetime

class Simulation():
    def __init__(self, N, T):
        self.N = N
        self.T = T

    def __call__(self):
        start_time = datetime.datetime.now()
        print("Simulation start. ")
        print(f'T = {self.T}')
        for t in range(self.T):
            print(f"Simulation time: {t + 1}")
            a = random.randint(0, 10)
            b = random.randint(0, self.T)
            print(f'{a} + {b} = {a + b}')
            time.sleep(1)  # todo: Find out why at the simulation code side there must be a time sleep as well
        print(f"Simulation finished in {datetime.datetime.now() - start_time}. ")