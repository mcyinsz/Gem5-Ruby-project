# 新建一个文件：run_scalability_tests.py
import subprocess
import os
from env import *
import time

def run_single_test(application, cpu_num, topology):
    cmd = [
        M5_EXE_PATH,
        MAIN_PATH,
        "--application", application,
        "--cpu-num", str(cpu_num),
        "--topology", topology
    ]
    
    print(f"Running: {' '.join(cmd)}")
    os.system(' '.join(cmd))

def main():
    for application in ["GeMM", "threads", "bad_cache"]:
        run_single_test(application, 1, "all2all")

    for application in ["GeMM", "threads", "bad_cache"]:
        for cpu_num in [2, 4, 8, 16]:
            run_single_test(application, cpu_num, "mesh")

if __name__ == "__main__":
    main()