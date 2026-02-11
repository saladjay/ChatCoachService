# Git Submodule 使用指南

Git Submodule 允许你将一个 Git 仓库作为另一个 Git 仓库的子目录，同时保持提交的独立性。

## 基本概念

Submodule 是一个独立的 Git 仓库，嵌入到主仓库中的特定路径。主仓库只记录 submodule 的特定提交 ID，而不是其完整内容。

## 常用命令示例

### 1. 添加 Submodule

```bash
# 基本语法
git submodule add <repository-url> <path>

# 示例：添加一个库到 libs/mylib 目录
git submodule add https://github.com/user/repo.git libs/mylib

# 添加并指定分支
git submodule add -b main https://github.com/user/repo.git libs/mylib
```

### 2. 克隆包含 Submodule 的仓库

```bash
# 方法一：克隆时同时初始化 submodules
git clone --recursive <repository-url>

# 方法二：先克隆，再初始化 submodules
git clone <repository-url>
cd <repository>
git submodule init
git submodule update

# 方法三：一条命令初始化并更新
git submodule update --init --recursive
```

### 3. 查看 Submodule 状态

```bash
# 查看所有 submodules 的状态
git submodule status

# 查看详细信息
git submodule

# 查看 submodule 配置
cat .gitmodules
```

### 4. 更新 Submodule

```bash
# 更新单个 submodule 到最新提交
cd <submodule-path>
git pull origin main

# 更新所有 submodules 到远程最新版本
git submodule update --remote

# 更新所有 submodules 到 .gitmodules 中指定的分支
git submodule update --remote --merge

# 更新并递归更新嵌套的 submodules
git submodule update --remote --recursive
```

### 5. 修改 Submodule 内容

```bash
# 进入 submodule 目录
cd <submodule-path>

# 创建或切换分支
git checkout -b feature-branch

# 进行修改并提交
git add .
git commit -m "Update submodule"
git push origin feature-branch

# 返回主仓库
cd ..

# 提交 submodule 的引用更新
git add <submodule-path>
git commit -m "Update submodule reference"
git push
```

### 6. 删除 Submodule

```bash
# 方法一：使用 git submodule deinit（推荐）
git submodule deinit -f <submodule-path>
rm -rf .git/modules/<submodule-path>
git rm -f <submodule-path>

# 方法二：手动删除
# 1. 删除 .gitmodules 中的相关配置
# 2. 删除 .git/config 中的相关配置
# 3. 执行以下命令
git rm --cached <submodule-path>
rm -rf <submodule-path>
rm -rf .git/modules/<submodule-path>
git commit -m "Remove submodule"
```

### 7. 同步 Submodule URL

```bash
# 当 submodule 的远程 URL 改变时
# 1. 更新 .gitmodules 文件中的 URL
# 2. 同步配置
git submodule sync --recursive

# 3. 更新 submodule
git submodule update --init --recursive
```

### 8. 遍历所有 Submodules 执行命令

```bash
# 在所有 submodules 中执行 git 命令
git submodule foreach 'git pull origin main'

# 递归执行（包括嵌套的 submodules）
git submodule foreach --recursive 'git checkout main'

# 查看所有 submodules 的状态
git submodule foreach 'git status'
```

### 9. 切换 Submodule 分支

```bash
# 进入 submodule
cd <submodule-path>

# 切换到指定分支
git checkout <branch-name>

# 返回主仓库并更新引用
cd ..
git add <submodule-path>
git commit -m "Switch submodule to <branch-name>"
```

### 10. 拉取主仓库更新（包括 Submodules）

```bash
# 拉取主仓库和所有 submodules 的更新
git pull --recurse-submodules

# 或者分步执行
git pull
git submodule update --init --recursive
```

## 实际工作流示例

### 场景一：首次设置项目

```bash
# 1. 克隆主仓库
git clone https://github.com/myteam/main-project.git
cd main-project

# 2. 初始化并更新所有 submodules
git submodule update --init --recursive

# 3. 开始工作
```

### 场景二：在 Submodule 中开发

```bash
# 1. 进入 submodule
cd libs/mylib

# 2. 确保在正确的分支上
git checkout main
git pull origin main

# 3. 创建功能分支
git checkout -b feature/new-feature

# 4. 进行开发和提交
git add .
git commit -m "Add new feature"
git push origin feature/new-feature

# 5. 返回主仓库
cd ../..

# 6. 更新主仓库中的 submodule 引用
git add libs/mylib
git commit -m "Update mylib submodule"
git push
```

### 场景三：团队协作更新

```bash
# 1. 拉取主仓库的最新更改
git pull

# 2. 更新 submodules 到主仓库记录的版本
git submodule update --recursive

# 3. 如果需要更新到 submodule 的最新版本
git submodule update --remote --merge
git add .
git commit -m "Update submodules to latest"
git push
```

## 常见问题

### Submodule 显示为修改状态

```bash
# 检查 submodule 状态
cd <submodule-path>
git status

# 如果有未提交的更改，提交它们
git add .
git commit -m "Commit changes"

# 或者重置到主仓库记录的版本
git reset --hard
```

### Submodule 目录为空

```bash
# 初始化并更新 submodules
git submodule update --init --recursive
```

### 更新冲突

```bash
# 在 submodule 中解决冲突
cd <submodule-path>
git status
# 解决冲突后
git add .
git commit -m "Resolve conflicts"

# 返回主仓库
cd ..
git add <submodule-path>
git commit -m "Update submodule after conflict resolution"
```

## 最佳实践

1. **始终提交 Submodule 的更改**：在主仓库中提交 submodule 引用之前，确保 submodule 的更改已经推送到远程
2. **使用特定的提交或标签**：避免直接跟踪 submodule 的分支头，使用特定的提交 ID 或标签
3. **文档化 Submodule**：在 README 中说明项目使用了 submodules 以及如何初始化它们
4. **定期同步**：定期运行 `git submodule update` 确保团队成员使用相同版本的 submodules
5. **谨慎使用 --remote**：`git submodule update --remote` 会更新到最新版本，可能引入不兼容的更改

## .gitmodules 文件示例

```ini
[submodule "libs/common"]
    path = libs/common
    url = https://github.com/myteam/common-lib.git
    branch = main

[submodule "third-party/vendor"]
    path = third-party/vendor
    url = https://github.com/vendor/library.git
    branch = stable
```

## 有用的配置

```bash
# 设置 git status 显示 submodule 摘要
git config status.submoduleSummary true

# 设置 git diff 显示 submodule 的详细差异
git config diff.submodule log

# 设置推送时检查 submodules
git config push.recurseSubmodules check

# 或者设置推送时自动推送 submodules
git config push.recurseSubmodules on-demand
```

---

**提示**：Git Submodule 适合管理独立的、有自己版本控制的依赖项。如果只是想共享代码，考虑使用包管理器或 Git Subtree 等替代方案。
