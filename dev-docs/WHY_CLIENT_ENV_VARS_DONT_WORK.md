# 为什么客户端环境变量不影响服务端

## 问题

在测试脚本中设置环境变量：

```bash
export USE_MERGE_STEP_PARALLEL=true
python tests/load_test.py ...
```

**这不会影响服务端的行为！**

## 原因

### 1. 环境变量的作用域

环境变量只在当前进程及其子进程中有效：

```
┌─────────────────────────────────────────────────────────────┐
│ 客户端机器                                                   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Bash Shell                                           │  │
│  │ export USE_MERGE_STEP_PARALLEL=true                  │  │
│  │                                                      │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │ Python Process (load_test.py)                  │ │  │
│  │  │ - 可以读取 USE_MERGE_STEP_PARALLEL=true        │ │  │
│  │  │ - 但只是发送 HTTP 请求                         │ │  │
│  │  │ - 不会传递环境变量给服务端                     │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP Request
                            │ (不包含环境变量)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 服务端机器                                                   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ FastAPI Server Process                               │  │
│  │ - 启动时读取 .env 文件                               │  │
│  │ - USE_MERGE_STEP_PARALLEL=true (从 .env)            │  │
│  │ - 运行期间不会改变                                   │  │
│  │ - 不受客户端环境变量影响                             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2. HTTP 协议的限制

HTTP 请求不传递环境变量：

```python
# 客户端 (load_test.py)
import os
os.environ['USE_MERGE_STEP_PARALLEL'] = 'true'  # 只在客户端有效

# 发送 HTTP 请求
response = requests.post(
    "http://server:8000/api/v1/predict",
    json={...}  # 只传递 JSON 数据，不传递环境变量
)
```

### 3. 服务端配置的生命周期

```python
# 服务端 (app/core/config.py)
class AppConfig(BaseSettings):
    use_merge_step_parallel: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",  # 启动时读取
        ...
    )

# 服务启动时
settings = AppConfig()  # 读取 .env，之后不会改变
```

**关键点：**
- 配置在服务启动时读取
- 运行期间不会重新读取
- 客户端请求不会影响配置

## 正确的测试方法

### 方法 1：使用服务端切换脚本（推荐）

```bash
# 在服务端机器上

# 切换到串行模式
./scripts/switch_server_mode.sh serial
./start_server.sh

# 运行测试（在客户端）
python tests/load_test.py --disable-cache --multi-images ...

# 切换到并行模式
./scripts/switch_server_mode.sh parallel
./start_server.sh

# 再次运行测试
python tests/load_test.py --disable-cache --multi-images ...
```

### 方法 2：手动修改 .env

```bash
# 在服务端机器上

# 测试串行模式
vim .env
# 修改: USE_MERGE_STEP_PARALLEL=false
./start_server.sh

# 测试并行模式
vim .env
# 修改: USE_MERGE_STEP_PARALLEL=true
./start_server.sh
```

### 方法 3：使用不同的服务实例

```bash
# 启动串行模式服务（端口 8000）
USE_MERGE_STEP_PARALLEL=false uvicorn app.main:app --port 8000 &

# 启动并行模式服务（端口 8001）
USE_MERGE_STEP_PARALLEL=true uvicorn app.main:app --port 8001 &

# 测试串行
python tests/load_test.py --url http://localhost:8000 ...

# 测试并行
python tests/load_test.py --url http://localhost:8001 ...
```

## 为什么原来的脚本是错误的

```bash
# scripts/test_serial_vs_parallel.sh (错误版本)

# 这只影响客户端，不影响服务端！
export USE_MERGE_STEP_PARALLEL=false
python tests/load_test.py ...  # 服务端仍然使用启动时的配置

# 这也只影响客户端！
export USE_MERGE_STEP_PARALLEL=true
python tests/load_test.py ...  # 服务端配置没有改变
```

**问题：**
- 两次测试实际上都使用相同的服务端配置
- 无法真正对比串行和并行模式
- 测试结果会相同或相似

## 正确的测试流程

### 完整测试流程（服务端和客户端分离）

**在服务端：**

```bash
# 1. 切换到串行模式
./scripts/switch_server_mode.sh serial

# 2. 重启服务
./start_server.sh

# 3. 验证模式
tail -f logs/server.log | grep "SERIAL\|PARALLEL"
# 应该看到: "Using merge_step optimized flow with SERIAL processing"
```

**在客户端：**

```bash
# 4. 运行串行测试
python tests/load_test.py \
  --url http://server:8000 \
  --concurrent 5 \
  --requests 20 \
  --disable-cache \
  --multi-images url1 url2 url3

# 记录结果: P50 ~21s
```

**再次在服务端：**

```bash
# 5. 切换到并行模式
./scripts/switch_server_mode.sh parallel

# 6. 重启服务
./start_server.sh

# 7. 验证模式
tail -f logs/server.log | grep "SERIAL\|PARALLEL"
# 应该看到: "Using merge_step optimized flow with PARALLEL processing"
```

**再次在客户端：**

```bash
# 8. 运行并行测试
python tests/load_test.py \
  --url http://server:8000 \
  --concurrent 5 \
  --requests 20 \
  --disable-cache \
  --multi-images url1 url2 url3

# 记录结果: P50 ~7s
```

### 自动化测试流程（服务端和客户端在同一机器）

```bash
#!/bin/bash
# complete_test.sh

echo "Testing SERIAL mode..."
./scripts/switch_server_mode.sh serial
./start_server.sh
sleep 5  # 等待服务启动
python tests/load_test.py --disable-cache --multi-images ... > serial_results.txt

echo "Testing PARALLEL mode..."
./scripts/switch_server_mode.sh parallel
./start_server.sh
sleep 5  # 等待服务启动
python tests/load_test.py --disable-cache --multi-images ... > parallel_results.txt

echo "Comparing results..."
diff serial_results.txt parallel_results.txt
```

## 如何验证服务端配置

### 方法 1：检查服务日志

```bash
# 启动服务后，查看日志
tail -f logs/server.log

# 串行模式应该看到：
# INFO - Using merge_step optimized flow with SERIAL processing
# INFO - Processing 3 images in SERIAL (one by one)

# 并行模式应该看到：
# INFO - Using merge_step optimized flow with PARALLEL processing
# INFO - Processing 3 images in PARALLEL
```

### 方法 2：检查响应时间

```bash
# 串行模式：~21s for 3 images
# 并行模式：~7s for 3 images

# 如果两次测试时间相同，说明服务端配置没有改变
```

### 方法 3：使用配置检查脚本

```bash
# 在服务端运行
./scripts/check_config.ps1  # Windows
python scripts/verify_serial_parallel.py  # Linux/Mac

# 输出当前配置
```

## 总结

### 关键点

1. **客户端环境变量不影响服务端**
   - 环境变量只在当前进程有效
   - HTTP 请求不传递环境变量

2. **服务端配置在启动时读取**
   - 从 .env 文件读取
   - 运行期间不会改变
   - 必须重启服务才能应用新配置

3. **正确的测试方法**
   - 在服务端修改 .env
   - 重启服务
   - 在客户端运行测试
   - 验证服务日志确认模式

### 可用的工具

- `scripts/switch_server_mode.sh` - 切换服务端模式（Linux/Mac）
- `scripts/switch_server_mode.ps1` - 切换服务端模式（Windows）
- `scripts/test_serial_vs_parallel_manual.sh` - 手动测试脚本
- `scripts/check_config.ps1` - 配置检查脚本

### 快速测试

```bash
# 在服务端机器上
./scripts/switch_server_mode.sh serial && ./start_server.sh
# 等待服务启动，然后在客户端运行测试

./scripts/switch_server_mode.sh parallel && ./start_server.sh
# 等待服务启动，然后在客户端运行测试
```
