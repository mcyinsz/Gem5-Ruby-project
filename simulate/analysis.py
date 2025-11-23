import os
import re
import csv
import argparse
import sys
from env import *
import datetime

def parse_filename(filename):
    """
    从文件名解析参数信息
    格式: stats-<application>-<cpu_num>-<cacheline_size_bytes>-<cache_size_kB>-<network_topology>-<network_flit_size>-<network_hop_latency>.txt
    """
    # 移除文件扩展名
    basename = os.path.basename(filename).replace('.txt', '')
    
    # 按连字符分割
    parts = basename.split('-')
    
    if len(parts) < 7:
        print(f"Warning: Unexpected filename format: {filename}")
        return {}
    
    try:
        params = {
            "Application": parts[1],
            "CPU_Num": int(parts[2]),
            "Cacheline_Size_Bytes": int(parts[3]),
            "Cachesize_kB": int(parts[4]),
            "Network_Topology": parts[5],
            "Network_Flit_Size": int(parts[6]),
            "Network_Hop_Latency": int(parts[7])
        }
        return params
    except (ValueError, IndexError) as e:
        print(f"Error parsing filename {filename}: {e}")
        return {}

def get_advanced_patterns():
    """
    定义高级统计指标的正则表达式
    """
    return {
        # --- 基础概览 ---
        "SimSeconds": r"simSeconds\s+([0-9\.e\-\+]+)",
        "Total_Insts": r"simInsts\s+(\d+)",
        "AvgIPC": r"system\.cpu[\d]*\.ipc\s+([0-9\.e\-\+]+)", 
        "cycles": r"system\.cpu[\d]*\.numCycles\s+([0-9\.e\-\+]+)", 
        
        # --- 关键一致性事件 (Coherence Events) ---
        # FwdGetM: 其他核想写，请求转发给拥有者 -> 意味着写竞争 (True Sharing / False Sharing)
        "Coh_FwdGetM (Write Contention)": r"system\.ruby\.L1Cache_Controller\.FwdGetM::total\s+(\d+)",
        # FwdGetS: 其他核想读，请求转发 -> 意味着读共享
        "Coh_FwdGetS (Read Sharing)": r"system\.ruby\.L1Cache_Controller\.FwdGetS::total\s+(\d+)",
        # Inv: 失效消息 -> 意味着有人在写共享数据
        "Coh_Invalidations": r"system\.ruby\.L1Cache_Controller\.Inv::total\s+(\d+)",
        # Writebacks: 数据写回下级缓存
        "Coh_Writebacks (PutAck)": r"system\.ruby\.L1Cache_Controller\.PutAck::total\s+(\d+)",
        # Locked RMW: 原子指令导致的锁操作 (通常是性能杀手)
        "Coh_Locked_RMW": r"system\.ruby\.RequestType\.Locked_RMW_.*::total\s+(\d+)",

        # --- 控制器瓶颈 (Controller Bottlenecks) ---
        # L1 Cache 控制器最忙的周期数 (反映私有缓存压力)
        "Max_L1_BusyCycles": r"system\.ruby\.controllers\d+\.fullyBusyCycles\s+(\d+)",
        # L1 输入队列平均阻塞时间 (反映 CPU 请求由于缓存忙而排队的时间)
        "L1_MandatoryQueue_Lat": r"system\.ruby\.controllers\d+\.mandatoryQueue\.m_avg_stall_time\s+([0-9\.e\-\+]+)",
        
        # --- 片上网络 (Interconnect / NoC) ---
        # 控制消息 (Request/Response) 的平均延迟 (VNet 0, 1)
        "NoC_Control_Lat": r"system\.ruby\.network\.average_flit_vnet_latency\s+\|\s*([0-9\.]+)\s*\|\s*([0-9\.]+)",
        # 数据消息 (Data) 的平均延迟 (VNet 2) - 如果带宽不足，这个值会飙升
        "NoC_Data_Lat": r"system\.ruby\.network\.average_flit_vnet_latency\s+.*\|\s*([0-9\.]+)\s*$",
        # 网络总注入量
        "NoC_Flits_Injected": r"system\.ruby\.network\.flits_injected::total\s+(\d+)",
        # 平均每一跳消耗的周期
        "NoC_Avg_Hops": r"system\.ruby\.network\.average_hops\s+([0-9\.e\-\+]+)",
        
        # --- 内存带宽 ---
        "DRAM_Read_BW": r"system\.mem_ctrl\.dram\.bwRead::total\s+([0-9\.e\-\+]+)",
        "DRAM_Write_BW": r"system\.mem_ctrl\.dram\.bwWrite::total\s+([0-9\.e\-\+]+)",
    }

def extract_max_from_matches(matches, convert_func=int):
    """从多个匹配中提取最大值（例如找出最忙的那个核）"""
    if not matches:
        return 0
    values = [convert_func(m) for m in matches]
    return max(values)

def extract_avg_from_matches(matches, convert_func=float):
    """从多个匹配中提取平均值"""
    if not matches:
        return 0
    values = [convert_func(m) for m in matches]
    return sum(values) / len(values)

def extract_middle_stats_block(content):
    """
    提取中间的那个统计块（真正需要的simulation output段）
    """
    # 使用正则表达式分割统计块
    blocks = re.split(r'---------- (?:Begin|End) Simulation Statistics\s+----------', content)
    
    # 过滤掉空字符串
    blocks = [block.strip() for block in blocks if block.strip()]
    
    # 应该有三个块，我们取中间的那个
    if len(blocks) >= 3:
        return blocks[1]  # 第二个块（索引为1）
    elif len(blocks) == 1:
        return blocks[0]  # 如果只有一个块，就用它
    else:
        print(f"Warning: Unexpected number of stats blocks: {len(blocks)}")
        return blocks[0] if blocks else ""

def parse_file(filepath):
    data = {}
    
    # 首先从文件名中提取参数
    filename_params = parse_filename(filepath)
    data.update(filename_params)
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            
            # 提取中间统计块
            stats_content = extract_middle_stats_block(content)
            if not stats_content:
                print(f"Warning: No valid stats block found in {filepath}")
                return None
            
            # 1. 基础提取
            patterns = get_advanced_patterns()
            
            # 针对 IPC 计算平均值
            ipc_matches = re.findall(patterns["AvgIPC"], stats_content)
            data["AvgIPC"] = extract_avg_from_matches(ipc_matches)

            cpu_cycles = re.findall(patterns["cycles"], stats_content)
            data["LoadBalance"] = extract_max_from_matches(cpu_cycles)/extract_avg_from_matches(cpu_cycles)

            # 针对 Coherence Events (直接取 Total)
            for key in ["Coh_FwdGetM (Write Contention)", "Coh_FwdGetS (Read Sharing)", 
                        "Coh_Invalidations", "Coh_Writebacks (PutAck)"]:
                match = re.search(patterns[key], stats_content)
                data[key] = int(match.group(1)) if match else 0

            # 针对 Locked RMW (可能有 Read 和 Write 两种，求和)
            rmw_matches = re.findall(patterns["Coh_Locked_RMW"], stats_content)
            data["Coh_Locked_RMW"] = sum([int(x) for x in rmw_matches])

            # 针对 Controller Busy (找出最忙的那个控制器，代表系统瓶颈)
            busy_matches = re.findall(r"system\.ruby\.controllers(\d+)\.fullyBusyCycles\s+(\d+)", stats_content)
            # 我们只关心 L1 控制器 (通常 ID 较小) 或 Directory (ID 较大)，这里取所有控制器的最大值作为系统"最堵"的程度
            if busy_matches:
                # busy_matches is [(id, cycles), (id, cycles)...]
                data["Max_Controller_BusyCycles"] = max([int(m[1]) for m in busy_matches])
            else:
                data["Max_Controller_BusyCycles"] = 0

            # 针对 Mandatory Queue Latency (取最大值，看哪个核被阻塞最久)
            q_matches = re.findall(r"system\.ruby\.controllers\d+\.mandatoryQueue\.m_avg_stall_time\s+([0-9\.e\-\+]+)", stats_content)
            data["Max_MandatoryQueue_Stall"] = extract_max_from_matches(q_matches, float)

            # 针对 NoC VNet Latency (Gem5 输出通常是 | val | val | val |)
            # 假设 VNet 0/1 是控制，VNet 2 是数据
            vnet_match = re.search(r"system\.ruby\.network\.average_flit_vnet_latency\s+\|([0-9\.\s]+)\|", stats_content)
            if vnet_match:
                parts = vnet_match.group(1).strip().split('|')
                # 清理空格
                vals = [float(x.strip()) for x in parts if x.strip()]
                if len(vals) >= 3:
                    data["NoC_Control_Lat"] = (vals[0] + vals[1]) / 2
                    data["NoC_Data_Lat"] = vals[2]
                elif len(vals) >= 1:
                    data["NoC_Control_Lat"] = vals[0]
                    data["NoC_Data_Lat"] = 0
            else:
                data["NoC_Control_Lat"] = 0
                data["NoC_Data_Lat"] = 0

            # 其他单值提取
            for key in ["SimSeconds", "NoC_Flits_Injected", "NoC_Avg_Hops", "DRAM_Read_BW"]:
                match = re.search(patterns[key], stats_content)
                data[key] = float(match.group(1)) if match else 0

            # --- 计算衍生指标 (Insight) ---
            
            # 1. 一致性与计算比 (Coherence per Instruction)
            # 如果这个值高，说明每执行少量指令就会触发昂贵的一致性操作
            total_insts = float(re.search(patterns["Total_Insts"], stats_content).group(1)) if re.search(patterns["Total_Insts"], stats_content) else 1
            data["Total_Insts"] = total_insts
            
            coherence_events = data["Coh_FwdGetM (Write Contention)"] + data["Coh_Invalidations"]
            data["Contention_Intensity"] = (coherence_events / total_insts) * 1000 # 每1000条指令的竞争次数

            # 2. 伪共享/真竞争 严重程度
            # 如果 FwdGetM 很高，说明多个核在争抢写权限
            data["Write_Contention_Count"] = data["Coh_FwdGetM (Write Contention)"]

            # 3. 阻塞程度
            # Mandatory Queue Stall Time 高说明 CPU 等待 L1 响应的时间长
            data["CPU_Stall_Severity"] = data["Max_MandatoryQueue_Stall"]

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None
    
    return data

def main():
    # --- 修改点 1: 定义输入目录 ---
    # 假设 GENERATED_DIR 和 RESULTS_DIR 来自 from env import *
    if 'GENERATED_DIR' not in globals() or 'RESULTS_DIR' not in globals():
        print("Error: GENERATED_DIR or RESULTS_DIR not defined in env.py")
        return

    input_dir = GENERATED_DIR
    
    # --- 修改点 2: 补全 output_file 并修复 datetime 语法 ---
    # 获取当前时间格式化字符串，例如: 2023-10-27_14-30-00
    current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(RESULTS_DIR, f"results-{current_time}.csv")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    results = []
    
    # 检查输入目录是否存在
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return

    # --- 修改点 3: 遍历逻辑不再依赖 args.input_dir，改用 input_dir ---
    print(f"Scanning directory: {input_dir}")
    for filename in os.listdir(input_dir):
        if filename.startswith("stats-") and filename.endswith(".txt"):
            filepath = os.path.join(input_dir, filename)
            print(f"Analyzing: {filepath}")
            row = parse_file(filepath)
            if row:
                row["Filename"] = filename  # 保留原始文件名用于参考
                results.append(row)

    if not results:
        print("No valid data found to process.")
        return

    # 确定列顺序 - 将文件名参数放在前面
    filename_cols = ["Filename", "Application", "CPU_Num", "Cacheline_Size_Bytes", "Cachesize_kB",
                     "Network_Topology", "Network_Flit_Size", "Network_Hop_Latency"]
    
    fixed_stats_cols = ["SimSeconds", "Total_Insts", "AvgIPC", "LoadBalance", "Contention_Intensity", 
                      "Write_Contention_Count", "Coh_Locked_RMW", "CPU_Stall_Severity",
                      "NoC_Control_Lat", "NoC_Data_Lat"]
    
    # 动态获取剩余列
    all_cols = set().union(*(d.keys() for d in results))
    remaining_cols = sorted([c for c in all_cols if c not in filename_cols and c not in fixed_stats_cols])
    final_cols = filename_cols + fixed_stats_cols + remaining_cols

    # --- 修改点 4: 写入逻辑不再依赖 args.output，改用 output_file ---
    try:
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=final_cols)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
                
        print(f"\nReport successfully generated: {output_file}")
        print(f"Processed {len(results)} files")
        print("CHECK: 'Contention_Intensity' and 'NoC_Data_Lat' to find bottlenecks.")
        
    except IOError as e:
        print(f"Error writing to file {output_file}: {e}")

if __name__ == "__main__":
    main()