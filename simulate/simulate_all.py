import subprocess
import os
from env import *
import time

def run_single_test(application, cpu_num, topology, hop_latency, cacheline_byte):
    cmd = [
        M5_EXE_PATH,
        MAIN_PATH,
        "--application", application,
        "--cpu-num", str(cpu_num),
        "--topology", topology,
        "--hop-latency", str(hop_latency),
        "--cacheline-byte", str(cacheline_byte)
    ]
    
    print(f"Running: {' '.join(cmd)}")
    os.system(' '.join(cmd))

def main():

    for application in ["Transpose_GeMM", "Matrix_symm", "FFT", "bad_cache"]:
        
        # 1. scale
        for cpu_num in [1,2,4,8,16]:
            run_single_test(application, cpu_num, "mesh", 1, 64)

        # 2. slow down
        for hop_latency in [1, 2, 4, 8]:
            run_single_test(application, 4, "mesh", hop_latency, 64)

        # 3. cacheline size
        for cacheline_size in [32, 64, 128, 256]:
            run_single_test(application, 4, "mesh", 1, cacheline_size)

if __name__ == "__main__":
    main()