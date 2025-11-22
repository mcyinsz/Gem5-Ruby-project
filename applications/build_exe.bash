# 确保在 applications 目录下
cd ~/gem5/configs/learning_gem5/MSI-cache-network-application/applications

# 定义 gem5 路径变量
GEM5_PATH=~/gem5
M5_LIB=${GEM5_PATH}/util/m5/build/x86/out/libm5.a
INCLUDE_DIR=${GEM5_PATH}/include

# 1. 编译 Bad_cache
g++ -O2 -I${INCLUDE_DIR} Bad_cache/src/Bad_cache.cpp ${M5_LIB} -o Bad_cache/bin/x86/linux/Bad_cache

# 2. 编译 FFT
g++ -O2 -I${INCLUDE_DIR} FFT/src/FFT.cpp ${M5_LIB} -o FFT/bin/x86/linux/FFT

# 3. 编译 GeMM
g++ -O2 -I${INCLUDE_DIR} GeMM/src/GeMM.cpp ${M5_LIB} -o GeMM/bin/x86/linux/GeMM

# 4. 编译 Matrix_symm
g++ -O2 -I${INCLUDE_DIR} Matrix_symm/src/Matrix_symm.cpp ${M5_LIB} -o Matrix_symm/bin/x86/linux/Matrix_symm

# 5. 编译 Transpose_GeMM
g++ -O2 -I${INCLUDE_DIR} Transpose_GeMM/src/Transpose_GeMM.cpp ${M5_LIB} -o Transpose_GeMM/bin/x86/linux/Transpose_GeMM