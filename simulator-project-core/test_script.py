import sys
import datetime
import random
import time

try:
    T = int(sys.argv[1])
except IndexError:
    print("No simulation time specified.")
    T = 10

start_time = datetime.datetime.now()
print("Simulation start. ")
print(f'T = {T}')
for t in range(T):
    print(f"Simulation time: {t+1}")
    a = random.randint(0,10)
    b = random.randint(0,T)
    print(f'{a} + {b} = {a+b}')
    time.sleep(1)  # todo: Find out why at the simulation code side there must be a time sleep as well
print(f"Simulation finished in {datetime.datetime.now() - start_time}. ")