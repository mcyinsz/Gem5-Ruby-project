#include <iostream>
#include <thread>
#include <vector>

using namespace std;

/*
 * 竞争调用测试程序
 * 模拟多个线程对共享数据的竞争访问
 * 使用与GeMM相同的线程分配模式
 */
void race_worker(double *shared_data, int *counters,
                 int tid, int threads,
                 int data_size, int iterations)
{
    // 每个线程处理从tid开始，步长为threads的数据块
    for (int iter = 0; iter < iterations; iter++) {
        for (int i = tid; i < data_size; i += threads) {
            // 频繁读写共享数据 - 触发缓存一致性协议
            double temp = shared_data[i];
            shared_data[i] = temp * 1.01 + (tid + 1); // 每个线程有轻微的差异

            // 更新计数器数组 - 可能产生伪共享
            counters[i % threads] = counters[i % threads] + 1;

            // 偶尔访问其他线程的数据区域
            if (iter % 10 == 0) {
                int other_idx = (i + threads / 2) % data_size;
                shared_data[other_idx] = shared_data[other_idx] * 0.99;
            }
        }

        // 所有线程竞争更新全局统计信息
        if (iter % 5 == 0) {
            // 模拟竞争：所有线程尝试更新相同的几个位置
            for (int j = 0; j < 3; j++) {
                int comp_idx = (tid * 7 + j) % threads;
                counters[comp_idx] = counters[comp_idx] + (iter % 3);
            }
        }
    }
}

int main(int argc, char *argv[])
{
    int data_size, iterations;

    if (argc == 1) {
        data_size = 10000;    // 数据大小
        iterations = 1000;    // 迭代次数
    } else if (argc == 3) {
        data_size = atoi(argv[1]);
        iterations = atoi(argv[2]);
        if (data_size <= 0 || iterations <= 0) {
            cerr << "Usage: " << argv[0] << " [data_size iterations]" << endl;
            cerr << "Where data_size and iterations are positive integers" << endl;
            return 1;
        }
    } else {
        cerr << "Usage: " << argv[0] << " [data_size iterations]" << endl;
        cerr << "Where data_size and iterations are positive integers" << endl;
        return 1;
    }

    unsigned cpus = thread::hardware_concurrency();

    cout << "Running on " << cpus << " cores. ";
    cout << "Data size: " << data_size << ", Iterations: " << iterations << endl;
    cout << "This program creates memory access patterns that trigger cache coherence protocols" << endl;

    // 分配共享数据
    double *shared_data = new double[data_size];
    int *counters = new int[cpus];  // 每个线程一个计数器

    if (!(shared_data && counters)) {
        cerr << "Allocation error!" << endl;
        return 2;
    }

    // 初始化数据
    cout << "Initializing data..." << endl;
    for (int i = 0; i < data_size; i++) {
        shared_data[i] = (i % 100) * 1.5;  // 一些初始模式
    }

    for (int i = 0; i < cpus; i++) {
        counters[i] = 0;
    }

    thread **threads = new thread*[cpus];

    cout << "Starting race condition simulation..." << endl;

    // 启动工作线程
    for (int i = 0; i < cpus - 1; i++) {
        threads[i] = new thread(race_worker, shared_data, counters, i, cpus, data_size, iterations);
    }

    // 主线程也参与工作（与GeMM相同的模式）
    race_worker(shared_data, counters, cpus - 1, cpus, data_size, iterations);

    cout << "Waiting for other threads to complete" << endl;

    for (int i = 0; i < cpus - 1; i++) {
        threads[i]->join();
    }

    delete[] threads;

    cout << "Validation..." << endl;

    // 验证：检查数据是否被正确修改
    bool valid = true;

    // 检查计数器总和是否合理
    int total_counters = 0;
    for (int i = 0; i < cpus; i++) {
        total_counters += counters[i];
    }

    // 预期的计数器操作：每个线程对每个元素操作iterations次
    // 但由于竞争，实际值会有差异
    int expected_min = data_size * iterations;

    cout << "Total counter operations: " << total_counters << endl;
    cout << "Expected minimum: " << expected_min << endl;

    if (total_counters >= expected_min) {
        cout << "✓ Counter validation passed - sufficient operations detected" << endl;
    } else {
        cout << "✗ Counter validation questionable" << endl;
        valid = false;
    }

    // 检查共享数据的变化
    int changed_elements = 0;
    for (int i = 0; i < data_size; i++) {
        double expected = (i % 100) * 1.5;
        if (abs(shared_data[i] - expected) > 0.1) {
            changed_elements++;
        }
    }

    cout << "Changed elements: " << changed_elements << " out of " << data_size << endl;

    if (changed_elements == data_size) {
        cout << "✓ Data modification validation passed" << endl;
    } else {
        cout << "✗ Not all elements were modified" << endl;
        valid = false;
    }

    if (valid) {
        cout << "Success! Cache coherence patterns were generated." << endl;

        // 输出一些统计信息
        cout << "\nCache coherence characteristics:" << endl;
        cout << "1. " << cpus << " threads competing for shared data" << endl;
        cout << "2. Frequent read-modify-write operations" << endl;
        cout << "3. Cross-thread data access patterns" << endl;
        cout << "4. Potential false sharing in counters array" << endl;

        delete[] shared_data;
        delete[] counters;
        return 0;
    } else {
        cout << "Validation showed some inconsistencies" << endl;
        delete[] shared_data;
        delete[] counters;
        return 2;
    }
}
