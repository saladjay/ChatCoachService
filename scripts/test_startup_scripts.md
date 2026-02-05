# Startup Scripts Testing Guide

## 改进内容

两个启动脚本 (`start_server.sh` 和 `start_server.ps1`) 现在会自动检查 `.venv` 是否存在，如果不存在会自动运行 `uv sync`。

## 测试场景

### 场景 1：.venv 不存在（首次运行）

**预期行为**：
1. 检测到 `.venv` 不存在
2. 检查 `uv` 是否安装
3. 如果 `uv` 已安装，运行 `uv sync`
4. 创建虚拟环境成功后继续启动服务器
5. 如果 `uv` 未安装，显示错误并退出

**测试步骤**：
```bash
# Linux/macOS
rm -rf .venv
./start_server.sh

# Windows
Remove-Item -Recurse -Force .venv
.\start_server.ps1
```

**预期输出**：
```
========================================
Starting ChatCoach API Server
========================================

Virtual environment not found. Running uv sync...
[uv sync output...]
✓ Virtual environment created successfully

Activating virtual environment...
✓ Virtual environment activated
...
```

### 场景 2：.venv 已存在（正常运行）

**预期行为**：
1. 跳过 `uv sync`
2. 直接激活虚拟环境
3. 继续启动服务器

**测试步骤**：
```bash
# Linux/macOS
./start_server.sh

# Windows
.\start_server.ps1
```

**预期输出**：
```
========================================
Starting ChatCoach API Server
========================================

Activating virtual environment...
✓ Virtual environment activated
...
```

### 场景 3：uv 未安装且 .venv 不存在

**预期行为**：
1. 检测到 `.venv` 不存在
2. 检测到 `uv` 未安装
3. 显示错误信息和安装指引
4. 退出脚本

**测试步骤**：
```bash
# 临时重命名 uv（模拟未安装）
# 然后运行脚本
```

**预期输出**：
```
========================================
Starting ChatCoach API Server
========================================

Virtual environment not found. Running uv sync...
Error: uv is not installed
Please install uv first: https://docs.astral.sh/uv/getting-started/installation/
```

### 场景 4：uv sync 失败

**预期行为**：
1. 检测到 `.venv` 不存在
2. 运行 `uv sync` 但失败
3. 显示错误信息
4. 退出脚本

**预期输出**：
```
========================================
Starting ChatCoach API Server
========================================

Virtual environment not found. Running uv sync...
[uv sync error output...]
Error: Failed to create virtual environment
Please run 'uv sync' manually
```

## 代码逻辑

### Bash 脚本 (start_server.sh)

```bash
# Check if .venv exists, if not run uv sync
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running uv sync..."
    if command -v uv > /dev/null 2>&1; then
        uv sync
        if [ $? -eq 0 ]; then
            echo "✓ Virtual environment created successfully"
        else
            echo "Error: Failed to create virtual environment"
            echo "Please run 'uv sync' manually"
            exit 1
        fi
    else
        echo "Error: uv is not installed"
        echo "Please install uv first: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    echo ""
fi
```

### PowerShell 脚本 (start_server.ps1)

```powershell
# Check if .venv exists, if not run uv sync
if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Running uv sync..." -ForegroundColor Yellow
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand) {
        uv sync
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Virtual environment created successfully" -ForegroundColor Green
        } else {
            Write-Host "Error: Failed to create virtual environment" -ForegroundColor Red
            Write-Host "Please run 'uv sync' manually" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "Error: uv is not installed" -ForegroundColor Red
        Write-Host "Please install uv first: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
        exit 1
    }
    Write-Host ""
}
```

## 优势

1. **自动化**：首次运行时自动创建虚拟环境
2. **用户友好**：清晰的错误信息和安装指引
3. **健壮性**：检查 `uv` 是否安装和 `uv sync` 是否成功
4. **向后兼容**：如果 `.venv` 已存在，行为与之前完全相同

## 注意事项

1. 需要确保 `uv` 已安装在系统 PATH 中
2. `uv sync` 会根据 `pyproject.toml` 和 `uv.lock` 创建虚拟环境
3. 如果 `uv sync` 失败，脚本会退出，用户需要手动解决问题

## 相关文件

- `start_server.sh`：Linux/macOS 启动脚本
- `start_server.ps1`：Windows PowerShell 启动脚本
- `pyproject.toml`：项目依赖配置
- `uv.lock`：依赖锁定文件
