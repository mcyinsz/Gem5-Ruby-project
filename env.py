import os

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
GENERATED_DIR = os.path.join(ROOT_DIR, "generated")
NETWORKS_DIR = os.path.join(ROOT_DIR, "networks")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")
APPLICATIONS_DIR = os.path.join(ROOT_DIR, "applications")

# must preset Gem5-related
M5_OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(ROOT_DIR))), "m5out")
M5_OUT_STATS_PATH = os.path.join(M5_OUT_DIR, "stats.txt")