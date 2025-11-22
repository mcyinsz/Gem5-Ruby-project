

#include <iostream>
#include <thread>
#include <vector>
#include <gem5/m5ops.h> 

using namespace std;

// Alternative version with 1D arrays for better cache performance
void gemm_worker_transposed(double *A, double *BT, double *C,
    int tid, int threads,
    int M, int N, int K) {
    for (int i = tid; i < M; i += threads) {
        for (int j = 0; j < N; j++) {
            double sum = 0.0;
            // 现在A和BT都是行主序访问
            for (int k = 0; k < K; k++) {
                sum += A[i * K + k] * BT[j * K + k];
            }
            C[i * N + j] = sum;
        }
    }
}

int main(int argc, char *argv[])
{
    int M, N, K;

    if (argc == 1) {
        M = 256;
        N = 256;
        K = 256;
    } else if (argc == 4) {
        M = atoi(argv[1]);
        N = atoi(argv[2]);
        K = atoi(argv[3]);
        if (M <= 0 || N <= 0 || K <= 0) {
            cerr << "Usage: " << argv[0] << " [M N K]" << endl;
            cerr << "Where M, N, K are positive matrix dimensions" << endl;
            return 1;
        }
    } else {
        cerr << "Usage: " << argv[0] << " [M N K]" << endl;
        cerr << "Where M, N, K are matrix dimensions for A[MxK] * B[KxN] = C[MxN]" << endl;
        return 1;
    }

    unsigned cpus = thread::hardware_concurrency();

    cout << "Running on " << cpus << " cores. ";
    cout << "Matrix dimensions: A[" << M << "x" << K << "] * B[" << K << "x" << N << "] = C[" << M << "x" << N << "]" << endl;

    // Using 1D arrays for better cache performance
    double *A, *B, *C;
    A = new double[M * K];
    B = new double[K * N];
    C = new double[M * N];

    if (!(A && B && C)) {
        cerr << "Allocation error!" << endl;
        return 2;
    }

    // Initialize matrices
    cout << "Initializing matrices..." << endl;
    for (int i = 0; i < M; i++) {
        for (int j = 0; j < K; j++) {
            A[i * K + j] = (i + j) % 7;  // Some pattern
        }
    }

    for (int i = 0; i < K; i++) {
        for (int j = 0; j < N; j++) {
            B[i * N + j] = (i * j) % 5;  // Some pattern
        }
    }

    for (int i = 0; i < M * N; i++) {
        C[i] = 0.0;
    }

    double *BT = new double[K * N];  // B的转置
    for (int i = 0; i < K; i++) {
        for (int j = 0; j < N; j++) {
            BT[j * K + i] = B[i * N + j];
        }
    }

    thread **threads = new thread*[cpus];

    cout << "Starting matrix multiplication..." << endl;
    m5_dump_reset_stats(0, 0);
    // Launch worker threads
    for (int i = 0; i < cpus - 1; i++) {
        threads[i] = new thread(gemm_worker_transposed, A, BT, C, i, cpus, M, N, K);
    }

    // Execute the last thread with this thread context to appease SE mode
    gemm_worker_transposed(A, BT, C, cpus - 1, cpus, M, N, K);

    cout << "Waiting for other threads to complete" << endl;

    for (int i = 0; i < cpus - 1; i++) {
        threads[i]->join();
    }
    m5_dump_reset_stats(0, 0);

    delete[] threads;

    cout << "Validating..." << flush;

    // Simple validation: check a few elements
    bool valid = true;
    int checks = min(10, M * N);  // Check up to 10 elements

    for (int check = 0; check < checks; check++) {
        int i = (check * 17) % M;  // Some pseudo-random indices
        int j = (check * 23) % N;

        double expected = 0.0;
        for (int k = 0; k < K; k++) {
            expected += A[i * K + k] * B[k * N + j];
        }

        if (abs(C[i * N + j] - expected) > 1e-6) {
            cerr << "C[" << i << "][" << j << "] is wrong.";
            cerr << " Expected " << expected;
            cerr << " Got " << C[i * N + j] << "." << endl;
            valid = false;
            break;
        }
    }

    if (valid) {
        cout << "Success!" << endl;

        // Print a small sample if matrices are small
        if (M <= 10 && N <= 10) {
            cout << "Sample of matrix C:" << endl;
            for (int i = 0; i < min(5, M); i++) {
                for (int j = 0; j < min(5, N); j++) {
                    cout << C[i * N + j] << " ";
                }
                cout << endl;
            }
        }

        delete[] A;
        delete[] B;
        delete[] C;
        return 0;
    } else {
        delete[] A;
        delete[] B;
        delete[] C;
        return 2;
    }
}
