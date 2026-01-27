"""
验证 Intimacy Check Prompt 集成

检查所有文件是否正确创建和配置
"""

import json
from pathlib import Path

def verify_intimacy_prompt():
    """验证 intimacy check prompt 的集成"""
    
    project_root = Path(__file__).parent.parent
    prompts_dir = project_root / "prompts"
    
    print("=" * 60)
    print("Intimacy Check Prompt 集成验证")
    print("=" * 60)
    print()
    
    # 1. 检查版本文件
    print("1. 版本文件:")
    versions = [
        "intimacy_check_v1.0-original.txt",
        "intimacy_check_v2.0-compact.txt"
    ]
    for version in versions:
        file_path = prompts_dir / "versions" / version
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   ✅ {version} ({size} bytes)")
        else:
            print(f"   ❌ {version} (不存在)")
    print()
    
    # 2. 检查元数据文件
    print("2. 元数据文件:")
    metadata = [
        "intimacy_check_v1.0-original.json",
        "intimacy_check_v2.0-compact.json"
    ]
    for meta in metadata:
        file_path = prompts_dir / "metadata" / meta
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            token_est = data.get('token_estimate', 0)
            print(f"   ✅ {meta} (token: {token_est})")
        else:
            print(f"   ❌ {meta} (不存在)")
    print()
    
    # 3. 检查 active 文件
    print("3. Active 版本:")
    active_file = prompts_dir / "active" / "intimacy_check.txt"
    if active_file.exists():
        size = active_file.stat().st_size
        print(f"   ✅ intimacy_check.txt ({size} bytes)")
    else:
        print(f"   ❌ intimacy_check.txt (不存在)")
    print()
    
    # 4. 检查 registry
    print("4. Registry 状态:")
    registry_file = prompts_dir / "registry.json"
    if registry_file.exists():
        with open(registry_file, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        if "intimacy_check" in registry.get("prompts", {}):
            versions_count = len(registry["prompts"]["intimacy_check"])
            print(f"   ✅ 已注册 {versions_count} 个版本")
            
            for v in registry["prompts"]["intimacy_check"]:
                print(f"      - {v['version']} (ID: {v.get('version_id', 'N/A')})")
        else:
            print(f"   ❌ intimacy_check 未在 registry 中")
        
        if "intimacy_check" in registry.get("active_versions", {}):
            active = registry["active_versions"]["intimacy_check"]
            print(f"   ✅ Active 版本: {active}")
        else:
            print(f"   ❌ 未设置 active 版本")
    else:
        print(f"   ❌ registry.json 不存在")
    print()
    
    # 5. Token 对比
    print("5. Token 优化:")
    try:
        v1_meta = prompts_dir / "metadata" / "intimacy_check_v1.0-original.json"
        v2_meta = prompts_dir / "metadata" / "intimacy_check_v2.0-compact.json"
        
        with open(v1_meta, 'r', encoding='utf-8') as f:
            v1_data = json.load(f)
        with open(v2_meta, 'r', encoding='utf-8') as f:
            v2_data = json.load(f)
        
        v1_tokens = v1_data.get('token_estimate', 0)
        v2_tokens = v2_data.get('token_estimate', 0)
        reduction = ((v1_tokens - v2_tokens) / v1_tokens * 100) if v1_tokens > 0 else 0
        
        print(f"   V1.0 (Original): {v1_tokens} tokens")
        print(f"   V2.0 (Compact):  {v2_tokens} tokens")
        print(f"   节省: {reduction:.1f}%")
    except Exception as e:
        print(f"   ❌ 无法读取 token 信息: {e}")
    print()
    
    # 6. 代码集成检查
    print("6. 代码集成:")
    impl_file = project_root / "app" / "services" / "intimacy_checker_impl.py"
    if impl_file.exists():
        with open(impl_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "_load_intimacy_prompt" in content:
            print(f"   ✅ _load_intimacy_prompt() 函数已添加")
        else:
            print(f"   ❌ _load_intimacy_prompt() 函数未找到")
        
        if "prompts" in content and "active" in content and "intimacy_check.txt" in content:
            print(f"   ✅ 从文件系统加载 prompt")
        else:
            print(f"   ❌ 未从文件系统加载")
    else:
        print(f"   ❌ intimacy_checker_impl.py 不存在")
    print()
    
    print("=" * 60)
    print("验证完成")
    print("=" * 60)


if __name__ == "__main__":
    verify_intimacy_prompt()
