import random
import time
import datetime

class Simulation():
    def __init__(self, N, T, logger, **params):
        self.N = N
        self.T = T

        self.logger = logger

        # Other params
        self.params = params

    def __call__(self):
        start_time = datetime.datetime.now()
        filename = self.params['name'] + start_time.strftime("%Y%m%d") if self.params['name'] != "" else ""

        '''
        Simulation starts here
        '''
        self.logger.info("Simulation start. ")
        self.logger.info(f'N = {self.N}, T = {self.T}')
        for t in range(self.T):
            self.logger.info(f"Simulation time: {t + 1}")
            a = random.randint(0, 10)
            b = random.randint(0, self.T)
            self.logger.info(f'{a} + {b} = {a + b}')
            time.sleep(1)  # todo: Find out why at the simulation code side there must be a time sleep as well
        if filename != "":
            self.logger.info(f"Log file printed in {filename}.txt")
        self.logger.info(f"Simulation finished in {datetime.datetime.now() - start_time}. ")