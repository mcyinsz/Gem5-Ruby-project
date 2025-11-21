# import the m5 (gem5) library created when gem5 is built
import m5

# import all of the SimObjects
from m5.objects import *

# Needed for running C++ threads
from env import *
m5.util.addToPath(M5_CONFIGS_DIR)
from common.FileSystemConfig import config_filesystem

# You can import ruby_caches_MI_example to use the MI_example protocol instead
# of the MSI protocol
# from msi_caches import MyCacheSystem
from msi_garnet_caches import MyCacheSystem
import shutil
import argparse

def collect_stats(new_name: str = "default"):
    source_path = M5_OUT_STATS_PATH
    destination_path = os.path.join(GENERATED_DIR, new_name)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    
    try:
        shutil.move(source_path, destination_path)
        print(f"move: {source_path} -> {destination_path}")
            
    except Exception as e:
        print(f"fail to move: {e}")

def simulate(
    # applications
    system_application: str = "bad_cache",
    # cpu/cache params
    system_cpu_num: int = 4,
    system_cache_line_bytes: int = 64,
    # network params
    system_network_topology: str = "all2all",
    system_network_flit_size: int = 16,
    system_network_hop_latency: int = 1,
):
    # create the system we are going to simulate
    system = System()
    system.cache_line_size.value = system_cache_line_bytes

    # Set the clock frequency of the system (and all of its children)
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = "1GHz"
    system.clk_domain.voltage_domain = VoltageDomain()

    # Set up the system
    system.mem_mode = "timing"  # Use timing accesses
    system.mem_ranges = [AddrRange("8192MiB")]  # Create an address range

    # Create a pair of simple CPUs
    system.cpu = [X86O3CPU() for i in range(system_cpu_num)] # X86TimingSimpleCPU()

    # Create a DDR3 memory controller and connect it to the membus
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]

    # create the interrupt controller for the CPU and connect to the membus
    for cpu in system.cpu:
        cpu.createInterruptController()

    # Create the Ruby System
    system.ruby = MyCacheSystem()
    system.ruby.setup(
        system, 
        system.cpu, 
        [system.mem_ctrl],
        network_topology=system_network_topology,
        network_flit_size=system_network_flit_size,
        network_hop_latency=system_network_hop_latency
    )

    # Run application and use the compiled ISA to find the binary
    # grab the specific path to the binary
    if system_application == "GeMM":
        binary = os.path.join(
            APPLICATIONS_DIR,
            "GeMM/bin/x86/linux/GeMM"
        )
        cmd = [binary, "64", "64", "64"]
    elif system_application == "threads":
        binary = os.path.join(
            APPLICATIONS_DIR,
            "threads/bin/x86/linux/threads"
        )
        cmd = [binary, "100000"]
    elif system_application == "bad_cache":
        binary = os.path.join(
            APPLICATIONS_DIR,
            "Bad_cache/bin/x86/linux/Bad_cache"
        )
        cmd = [binary, "1000", "100"]
    elif system_application == "producer_consumer":
        binary = os.path.join(
            APPLICATIONS_DIR,
            "producer_consumer/bin/x86/linux/producer_consumer"
        )
        cmd = [binary]
    elif system_application == "Transpose_GeMM":
        binary = os.path.join(
            APPLICATIONS_DIR,
            "Transpose_GeMM/bin/x86/linux/Transpose_GeMM"
        )
        cmd = [binary, "64", "64", "64"]
    else:
        raise Exception("invalid application")

    

    # Create a process for a simple "multi-threaded" application
    process = Process()
    # Set the command
    # cmd is a list which begins with the executable (like argv)
    process.cmd = cmd
    # Set the cpu to use the process as its workload and create thread contexts
    for cpu in system.cpu:
        cpu.workload = process
        cpu.createThreads()

    system.workload = SEWorkload.init_compatible(binary)

    # Set up the pseudo file system for the threads function above
    config_filesystem(system)

    # set up the root SimObject and start the simulation
    root = Root(full_system=False, system=system)
    # instantiate all of the objects we've created above
    m5.instantiate()

    print("Beginning simulation!")
    exit_event = m5.simulate()
    print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

    # move stats file
    collect_stats(
        "-".join(["stats",system_application, str(system_cpu_num), str(system_cache_line_bytes), system_network_topology, str(system_network_flit_size), str(system_network_hop_latency)])+".txt"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--application", type=str, default="threads")
    parser.add_argument("--cpu-num", type=int, default=1) 
    parser.add_argument("--cacheline-byte", type=int, default=64)
    parser.add_argument("--topology", type=str, default="all2all")
    parser.add_argument("--flit-size", type=int, default=16)
    parser.add_argument("--hop-latency", type=int, default=1)
    args = parser.parse_args()
    
    simulate(
        system_application=args.application,
        system_cpu_num=args.cpu_num,
        system_cache_line_bytes=args.cacheline_byte,
        system_network_topology=args.topology,
        system_network_flit_size=args.flit_size,
        system_network_hop_latency=args.hop_latency
    )

main()