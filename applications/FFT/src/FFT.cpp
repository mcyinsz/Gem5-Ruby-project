#include <iostream>
#include <thread>
#include <vector>
#include <complex>
#include <cmath>
#include <atomic>
#include <algorithm>
#include <new> // for hardware_destructive_interference_size
#include <gem5/m5ops.h> 

using namespace std;

typedef complex<double> Complex;

#ifdef __cpp_lib_hardware_interference_size
    constexpr std::size_t CACHE_LINE_SIZE = std::hardware_destructive_interference_size;
#else
    // 默认为 128，足以覆盖大多数架构 (x86: 64, Apple/ARM: 128)
    constexpr std::size_t CACHE_LINE_SIZE = 128;
#endif

// 【核心修改】使用结构体并强制对齐，解决伪共享(False Sharing)问题
// 确保 counter 和 generation 位于不同的 Cache Line (64字节)
struct alignas(CACHE_LINE_SIZE) PaddedAtomicInt {
    std::atomic<int> val;
    // 填充字节，确保占据整个缓存行，防止相邻变量由于预取等机制产生干扰
    char pad[CACHE_LINE_SIZE - sizeof(std::atomic<int>)]; 
    
    PaddedAtomicInt() : val(0) {}
};

class SpinBarrier {
private:
    // 将两个原子变量分开定义，并利用上面的 Padding 结构
    PaddedAtomicInt counter;
    PaddedAtomicInt generation;
    int threshold;

public:
    explicit SpinBarrier(int count) : threshold(count) {
        counter.val.store(0);
        generation.val.store(0);
    }

    void wait() {
        if (threshold <= 1) return;

        // 获取当前代数 (只读 generation 行)
        int gen = generation.val.load(std::memory_order_acquire);
        
        // 原子加1 (只写 counter 行，不会 invalidated generation 行)
        int cur = counter.val.fetch_add(1);

        if (cur == threshold - 1) {
            // 最后一个到达的线程
            counter.val.store(0);
            // 只有这里会更新 generation，通知其他线程
            generation.val.fetch_add(1, std::memory_order_release);
        } else {
            // 等待线程
            // 指数退避参数
            int backoff = 100; 
            
            // 循环检查 generation
            while (generation.val.load(std::memory_order_relaxed) == gen) {
                // 本地空转，减少总线压力
                for (volatile int i = 0; i < backoff; ++i) {
                    __asm__ __volatile__("nop");
                }
                // 限制最大等待时间，防止响应过慢
                if (backoff < 100000) backoff *= 2;
            }
            std::atomic_thread_fence(std::memory_order_acquire);
        }
    }
};

// --- 以下 FFT 逻辑保持不变 ---

void bit_reverse(vector<Complex>& data) {
    int n = data.size();
    int j = 0;
    for (int i = 0; i < n - 1; i++) {
        if (i < j) swap(data[i], data[j]);
        int k = n >> 1;
        while (k <= j) { j -= k; k >>= 1; }
        j += k;
    }
}

void fft_worker(vector<Complex>& data, int tid, int num_threads, 
                SpinBarrier& barrier, int n, bool inverse) {
    
    int total_pairs = n / 2;
    int chunk = total_pairs / num_threads;
    int remainder = total_pairs % num_threads;
    
    int start_k = tid * chunk + min(tid, remainder);
    int end_k = start_k + chunk + (tid < remainder ? 1 : 0);

    for (int len = 2; len <= n; len <<= 1) {
        double base_angle = 2 * M_PI / len * (inverse ? 1 : -1);
        
        for (int k = start_k; k < end_k; ++k) {
            int pairs_per_group = len / 2;
            int group_idx = k / pairs_per_group;
            int j = k % pairs_per_group;
            int i = group_idx * len;
            
            int idx1 = i + j;
            int idx2 = i + j + len / 2;
            
            double angle = base_angle * j;
            Complex w(cos(angle), sin(angle));
            
            Complex u = data[idx1];
            Complex v = w * data[idx2];
            
            data[idx1] = u + v;
            data[idx2] = u - v;
        }
        
        barrier.wait(); 
    }
}

void parallel_fft(vector<Complex>& data, bool inverse = false) {
    int n = data.size();
    unsigned num_threads = thread::hardware_concurrency();
    if (num_threads == 0) num_threads = 1;
    if (num_threads > (unsigned)n/2) num_threads = n/2;
    
    // 如果硬件只有1核，或者数据量太小，回退到单线程（但在本次测试中，为了验证4核，我们允许它跑）
    if (num_threads <= 1) { 
        // 简单起见，这里复用 worker 但不创建线程
        SpinBarrier dummy(1);
        bit_reverse(data);
        fft_worker(data, 0, 1, dummy, n, inverse);
        return;
    }

    bit_reverse(data);
    vector<thread> threads;
    // 使用 new 在堆上分配 barrier，确保对齐生效（栈上有时不受控）
    SpinBarrier* barrier = new SpinBarrier(num_threads);
    
    for (int i = 0; i < (int)num_threads - 1; ++i) {
        threads.emplace_back(fft_worker, ref(data), i, num_threads, 
                           ref(*barrier), n, inverse);
    }
    
    fft_worker(data, num_threads - 1, num_threads, *barrier, n, inverse);
    
    for (auto& t : threads) {
        if (t.joinable()) t.join();
    }
    
    if (inverse) {
        for (int i = 0; i < n; ++i) data[i] /= n;
    }
    delete barrier;
}

bool validate(const vector<Complex>& res, const vector<Complex>& ref) {
    double max_err = 0.0;
    for (size_t i = 0; i < res.size(); ++i) {
        max_err = max(max_err, abs(res[i] - ref[i]));
    }
    return max_err < 1e-5;
}

// 串行参考用于验证
void serial_fft_ref(vector<Complex>& data) {
    int n = data.size();
    bit_reverse(data);
    for (int len = 2; len <= n; len <<= 1) {
        double angle = 2 * M_PI / len * -1;
        Complex wlen(cos(angle), sin(angle));
        for (int i = 0; i < n; i += len) {
            Complex w(1);
            for (int j = 0; j < len / 2; j++) {
                Complex u = data[i + j];
                Complex v = w * data[i + j + len / 2];
                data[i + j] = u + v;
                data[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

int main() {
    // 【重要建议】增大 N，让计算时间大于同步时间，减少屏障压力
    const int N = 4096; 
    
    cout << "FFT Test with N = " << N << endl;
    
    vector<Complex> signal(N);
    for(int i=0; i<N; ++i) signal[i] = sin(0.1*i) + sin(0.5*i);
    
    vector<Complex> ref_sig = signal;
    serial_fft_ref(ref_sig); // 串行计算正确答案
    
    cout << "1. Testing FFT..." << endl;
    m5_dump_reset_stats(0, 0);
    parallel_fft(signal, false);
    m5_dump_reset_stats(0, 0);

    if (validate(signal, ref_sig)) {
        cout << "✓ FFT Passed" << endl;
    } else {
        cout << "✗ FFT Failed" << endl;
    }
    
    // 逆变换测试省略或自行添加，只验证正变换通过即可说明同步逻辑正确

    return 0;
}