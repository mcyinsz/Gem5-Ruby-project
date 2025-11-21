import subprocess
import os
from env import *
import time

def run_single_test(application, cpu_num, topology, hop_latency):
    cmd = [
        M5_EXE_PATH,
        MAIN_PATH,
        "--application", application,
        "--cpu-num", str(cpu_num),
        "--topology", topology,
        "--hop-latency", str(hop_latency)
    ]
    
    print(f"Running: {' '.join(cmd)}")
    os.system(' '.join(cmd))

def main():

    for application in ["Opt_GeMM"]:# ["bad_cache", "GeMM"]:
        for hop_latency in [1,]:# 2, 4, 8]:
            run_single_test(application, 1, "all2all", hop_latency)
            run_single_test(application, 4, "mesh", hop_latency)

if __name__ == "__main__":
    main()