#include <iostream>
#include <thread>
#include <vector>
#include <cmath>
#include <gem5/m5ops.h> 

using namespace std;

/*
 * Matrix Symmetrization: C = (A + A^T) / 2
 * 写入模式与GEMM完全不同：
 * - GEMM: 每个线程连续写入结果矩阵的行
 * - 本程序: 每个线程需要同时写入对称位置的两个元素 C[i][j] 和 C[j][i]
 * - 这会导致更多的缓存一致性流量和潜在的写入冲突
 */
void matrix_symmetrize_worker(double *A, double *C,
                             int tid, int threads,
                             int N)
{
    // 每个线程处理矩阵的一组行，但写入模式特殊
    for (int i = tid; i < N; i += threads) {
        for (int j = i; j < N; j++) {  // 只处理上三角（包括对角线）
            double symmetric_value = (A[i * N + j] + A[j * N + i]) / 2.0;
            
            // 关键的不同写入模式：同时写入对称位置
            C[i * N + j] = symmetric_value;
            C[j * N + i] = symmetric_value;  // 对称位置
        }
    }
}

/*
 * 另一种写入模式：分块对称化
 * 每个线程处理矩阵的一个块，但需要写入对称的块
 */
void matrix_symmetrize_block_worker(double *A, double *C,
                                   int tid, int threads,
                                   int N)
{
    int block_size = 32;  // 块大小，可以根据缓存调整
    
    // 计算总块数
    int num_blocks = (N + block_size - 1) / block_size;
    
    // 每个线程处理一组块
    for (int block_idx = tid; block_idx < num_blocks * num_blocks; block_idx += threads) {
        int block_i = block_idx / num_blocks;
        int block_j = block_idx % num_blocks;
        
        // 只处理上三角块（包括对角线）
        if (block_i <= block_j) {
            int start_i = block_i * block_size;
            int start_j = block_j * block_size;
            int end_i = min(start_i + block_size, N);
            int end_j = min(start_j + block_size, N);
            
            // 处理当前块
            for (int i = start_i; i < end_i; i++) {
                for (int j = start_j; j < end_j; j++) {
                    if (i <= j) {  // 只处理上三角
                        double symmetric_value = (A[i * N + j] + A[j * N + i]) / 2.0;
                        C[i * N + j] = symmetric_value;
                        C[j * N + i] = symmetric_value;
                    }
                }
            }
        }
    }
}

/*
 * 验证函数：检查结果矩阵是否对称
 */
bool validate_symmetric(double *C, int N) {
    cout << "Validating symmetry..." << flush;
    
    // 检查矩阵是否对称
    for (int i = 0; i < min(100, N); i++) {  // 检查前100行以减少验证时间
        for (int j = i + 1; j < min(100, N); j++) {
            if (abs(C[i * N + j] - C[j * N + i]) > 1e-10) {
                cerr << "Asymmetry detected at (" << i << "," << j << "): " 
                     << C[i * N + j] << " vs " << C[j * N + i] << endl;
                return false;
            }
        }
    }
    
    // 检查对角线元素是否合理
    for (int i = 0; i < min(50, N); i++) {
        if (C[i * N + i] < 0 || isnan(C[i * N + i])) {
            cerr << "Invalid diagonal element at " << i << ": " << C[i * N + i] << endl;
            return false;
        }
    }
    
    return true;
}

int main(int argc, char *argv[])
{
    int N;

    if (argc == 1) {
        N = 512;  // 默认矩阵大小
    } else if (argc == 2) {
        N = atoi(argv[1]);
        if (N <= 0) {
            cerr << "Usage: " << argv[0] << " [N]" << endl;
            cerr << "Where N is the dimension of the square matrix A[NxN]" << endl;
            return 1;
        }
    } else {
        cerr << "Usage: " << argv[0] << " [N]" << endl;
        cerr << "Where N is the dimension of the square matrix A[NxN]" << endl;
        return 1;
    }

    unsigned cpus = thread::hardware_concurrency();

    cout << "Running on " << cpus << " cores. ";
    cout << "Matrix dimension: " << N << "x" << N << endl;
    cout << "Operation: C = (A + A^T) / 2" << endl;

    // 分配内存
    double *A, *C;
    A = new double[N * N];
    C = new double[N * N];

    if (!(A && C)) {
        cerr << "Allocation error!" << endl;
        return 2;
    }

    // 初始化原始矩阵A（非对称）
    cout << "Initializing matrix A..." << endl;
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            // 创建非对称矩阵，对角线元素较大
            if (i == j) {
                A[i * N + j] = 1.0 + (i % 10) * 0.1;  // 对角线元素
            } else {
                A[i * N + j] = (i * 0.3 + j * 0.7) / N;  // 非对角线元素
            }
        }
    }

    // 初始化结果矩阵C
    for (int i = 0; i < N * N; i++) {
        C[i] = 0.0;
    }

    vector<thread> threads;
    threads.reserve(cpus - 1);

    cout << "Starting matrix symmetrization..." << endl;
    m5_dump_reset_stats(0, 0);
    // 启动工作线程
    for (int i = 0; i < cpus - 1; i++) {
        // 可以选择使用基本版本或分块版本
        threads.emplace_back(matrix_symmetrize_worker, A, C, i, cpus, N);
        // threads.emplace_back(matrix_symmetrize_block_worker, A, C, i, cpus, N);
    }

    // 主线程也参与计算
    matrix_symmetrize_worker(A, C, cpus - 1, cpus, N);

    cout << "Waiting for other threads to complete..." << endl;

    // 等待所有线程完成
    for (auto &t : threads) {
        t.join();
    }
    m5_dump_reset_stats(0, 0);

    // 验证结果
    if (validate_symmetric(C, N)) {
        cout << "Success! Matrix is symmetric." << endl;

        // 如果矩阵较小，打印样本
        if (N <= 10) {
            cout << "Original matrix A (upper triangle):" << endl;
            for (int i = 0; i < N; i++) {
                for (int j = 0; j < N; j++) {
                    if (j >= i) cout << A[i * N + j] << "\t";
                    else cout << "-\t";
                }
                cout << endl;
            }
            
            cout << "Symmetric matrix C:" << endl;
            for (int i = 0; i < N; i++) {
                for (int j = 0; j < N; j++) {
                    cout << C[i * N + j] << "\t";
                }
                cout << endl;
            }
        } else {
            // 打印一些统计信息
            double trace = 0.0;
            for (int i = 0; i < N; i++) {
                trace += C[i * N + i];
            }
            cout << "Matrix trace: " << trace << endl;
            
            // 检查对称性误差
            double max_asymmetry = 0.0;
            for (int i = 0; i < min(100, N); i++) {
                for (int j = i + 1; j < min(100, N); j++) {
                    double asymmetry = abs(C[i * N + j] - C[j * N + i]);
                    if (asymmetry > max_asymmetry) {
                        max_asymmetry = asymmetry;
                    }
                }
            }
            cout << "Maximum asymmetry: " << max_asymmetry << endl;
        }

        delete[] A;
        delete[] C;
        return 0;
    } else {
        cerr << "Validation failed!" << endl;
        delete[] A;
        delete[] C;
        return 2;
    }
}