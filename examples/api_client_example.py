"""API 客户端示例 - 演示如何通过 HTTP API 调用服务

这个示例展示了：
1. 启动 FastAPI 服务器
2. 通过 HTTP 请求调用 API
3. 处理响应和错误

使用方法:
1. 启动服务器: uvicorn app.main:app --reload
2. 运行此脚本: python examples/api_client_example.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import httpx


async def call_generate_api():
    """调用生成回复 API"""
    
    # API 端点
    base_url = "http://localhost:8000"
    endpoint = "/api/v1/generate/reply"
    
    # 请求数据
    request_data = {
        "user_id": "user_123",
        "target_id": "target_456",
        "conversation_id": "conv_789",
        "language": "en",  # Supports: en, ar, pt, es, zh-CN
        "quality": "normal",
        "force_regenerate": False
    }
    
    print("=" * 80)
    print("API 客户端示例")
    print("=" * 80)
    print()
    print(f"请求 URL: {base_url}{endpoint}")
    print(f"请求数据: {request_data}")
    print()
    
    # 发送请求
    async with httpx.AsyncClient() as client:
        try:
            print("发送请求...")
            response = await client.post(
                f"{base_url}{endpoint}",
                json=request_data,
                timeout=60.0  # 60秒超时
            )
            
            print(f"状态码: {response.status_code}")
            print()
            
            if response.status_code == 200:
                # 成功响应
                data = response.json()
                
                print("=" * 80)
                print("生成成功")
                print("=" * 80)
                print()
                print(f"回复内容:")
                print(f"  {data['reply_text']}")
                print()
                print(f"元数据:")
                print(f"  - 置信度: {data['confidence']:.2f}")
                print(f"  - 亲密度(前): {data['intimacy_level_before']}/5")
                print(f"  - 亲密度(后): {data['intimacy_level_after']}/5")
                print(f"  - 使用模型: {data['model']}")
                print(f"  - 提供商: {data['provider']}")
                print(f"  - 成本: ${data['cost_usd']:.4f}")
                print(f"  - 是否降级: {data['fallback']}")
                
            elif response.status_code == 422:
                # 验证错误
                error = response.json()
                print("=" * 80)
                print("验证错误")
                print("=" * 80)
                print()
                print(f"错误详情: {error}")
                
            elif response.status_code == 402:
                # 配额超限
                error = response.json()
                print("=" * 80)
                print("配额超限")
                print("=" * 80)
                print()
                print(f"错误信息: {error.get('message', 'Unknown error')}")
                
            elif response.status_code == 500:
                # 服务器错误
                error = response.json()
                print("=" * 80)
                print("服务器错误")
                print("=" * 80)
                print()
                print(f"错误信息: {error.get('message', 'Unknown error')}")
                
            else:
                print(f"未知状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                
        except httpx.ConnectError:
            print("=" * 80)
            print("连接错误")
            print("=" * 80)
            print()
            print("无法连接到服务器。请确保:")
            print("1. 服务器已启动: uvicorn app.main:app --reload")
            print("2. 服务器地址正确: http://localhost:8000")
            
        except httpx.TimeoutException:
            print("=" * 80)
            print("请求超时")
            print("=" * 80)
            print()
            print("请求超过 60 秒未响应。")
            
        except Exception as e:
            print("=" * 80)
            print("未知错误")
            print("=" * 80)
            print()
            print(f"错误类型: {type(e).__name__}")
            print(f"错误信息: {str(e)}")


async def test_health_check():
    """测试健康检查端点"""
    
    base_url = "http://localhost:8000"
    
    print("\n" + "=" * 80)
    print("健康检查")
    print("=" * 80 + "\n")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ 服务状态: {data['status']}")
                print(f"✓ 服务版本: {data['version']}")
            else:
                print(f"✗ 健康检查失败: {response.status_code}")
                
        except httpx.ConnectError:
            print("✗ 无法连接到服务器")


async def test_different_qualities():
    """测试不同质量等级"""
    
    base_url = "http://localhost:8000"
    endpoint = "/api/v1/generate/reply"
    
    print("\n" + "=" * 80)
    print("测试不同质量等级")
    print("=" * 80 + "\n")
    
    qualities = ["cheap", "normal", "premium"]
    
    async with httpx.AsyncClient() as client:
        for quality in qualities:
            print(f"测试质量等级: {quality}")
            print("-" * 40)
            
            request_data = {
                "user_id": f"user_{quality}",
                "target_id": "target_test",
                "conversation_id": f"conv_{quality}",
                "quality": quality,
            }
            
            try:
                response = await client.post(
                    f"{base_url}{endpoint}",
                    json=request_data,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✓ 模型: {data['provider']}/{data['model']}")
                    print(f"✓ 成本: ${data['cost_usd']:.4f}")
                    print(f"✓ 回复: {data['reply_text'][:50]}...")
                else:
                    print(f"✗ 失败: {response.status_code}")
                    
            except Exception as e:
                print(f"✗ 错误: {str(e)}")
            
            print()


async def test_validation_errors():
    """测试验证错误"""
    
    base_url = "http://localhost:8000"
    endpoint = "/api/v1/generate/reply"
    
    print("\n" + "=" * 80)
    print("测试验证错误")
    print("=" * 80 + "\n")
    
    # 测试用例
    test_cases = [
        {
            "name": "缺少 user_id",
            "data": {
                "target_id": "target_123",
                "conversation_id": "conv_123",
            }
        },
        {
            "name": "空 user_id",
            "data": {
                "user_id": "",
                "target_id": "target_123",
                "conversation_id": "conv_123",
            }
        },
        {
            "name": "无效的 quality",
            "data": {
                "user_id": "user_123",
                "target_id": "target_123",
                "conversation_id": "conv_123",
                "quality": "invalid",
            }
        },
    ]
    
    async with httpx.AsyncClient() as client:
        for test_case in test_cases:
            print(f"测试: {test_case['name']}")
            print("-" * 40)
            
            try:
                response = await client.post(
                    f"{base_url}{endpoint}",
                    json=test_case['data'],
                    timeout=10.0
                )
                
                if response.status_code == 422:
                    print(f"✓ 正确返回 422 验证错误")
                    error = response.json()
                    print(f"  错误详情: {error.get('detail', 'N/A')}")
                else:
                    print(f"✗ 意外状态码: {response.status_code}")
                    
            except Exception as e:
                print(f"✗ 错误: {str(e)}")
            
            print()


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                         API 客户端示例                                      ║
║                                                                            ║
║  使用前请确保服务器已启动:                                                  ║
║  $ uvicorn app.main:app --reload                                          ║
║                                                                            ║
║  或者使用 Mock 模式（不需要真实 LLM API）:                                  ║
║  $ ORCHESTRATOR_MODE=mock uvicorn app.main:app --reload                   ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # 运行示例
    asyncio.run(test_health_check())
    asyncio.run(call_generate_api())
    
    # 可选：运行其他测试
    # asyncio.run(test_different_qualities())
    # asyncio.run(test_validation_errors())
