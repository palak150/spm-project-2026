import os
import time

print(f"Demo worker started. PID={os.getpid()}", flush=True)
counter = 0
while True:
    counter += 1
    print(f"Worker heartbeat {counter}", flush=True)
    time.sleep(2)
