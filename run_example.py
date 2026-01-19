"""运行示例的辅助脚本

使用方法:
    python run_example.py complete    # 运行完整流程示例
    python run_example.py simple      # 运行简化示例
    python run_example.py mock        # 运行 Mock 模式示例
    python run_example.py api         # 运行 API 客户端示例
"""

import sys
import subprocess
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    example_type = sys.argv[1].lower()
    
    # 确保从项目根目录运行
    project_root = Path(__file__).parent
    
    if example_type == "complete":
        print("运行完整流程示例...")
        subprocess.run([
            sys.executable,
            str(project_root / "examples" / "complete_flow_example.py")
        ])
    
    elif example_type == "simple":
        print("运行简化示例...")
        # 修改 complete_flow_example.py 中的 main() 为 simple_example()
        print("请编辑 examples/complete_flow_example.py")
        print("将最后的 asyncio.run(main()) 改为 asyncio.run(simple_example())")
    
    elif example_type == "mock":
        print("运行 Mock 模式示例...")
        print("请编辑 examples/complete_flow_example.py")
        print("将最后的 asyncio.run(main()) 改为 asyncio.run(mock_example())")
    
    elif example_type == "api":
        print("运行 API 客户端示例...")
        print("请先启动服务器: uvicorn app.main:app --reload")
        print("然后运行: python examples/api_client_example.py")
    
    else:
        print(f"未知的示例类型: {example_type}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
