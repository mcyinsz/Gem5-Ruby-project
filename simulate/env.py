import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
GENERATED_DIR = os.path.join(ROOT_DIR, "generated")
NETWORKS_DIR = os.path.join(ROOT_DIR, "networks")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")
APPLICATIONS_DIR = os.path.join(ROOT_DIR, "applications")
MAIN_PATH = os.path.join(ROOT_DIR, "simulate/main.py")
M5_OUT_DIR = os.path.join("./", "m5out")

# must preset Gem5-related
M5_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(ROOT_DIR)))
M5_EXE_PATH = os.path.join(M5_ROOT_DIR, "build/X86_MSI_Garnet/gem5.opt")
M5_CONFIGS_DIR = os.path.join(M5_ROOT_DIR, "configs")
M5_OUT_STATS_PATH = os.path.join(M5_OUT_DIR, "stats.txt")