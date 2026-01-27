#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的Screenshot分析客户端

这是一个简化版本，展示核心调用流程。

使用方法:
    python examples/simple_screenshot_client.py
"""

import asyncio
import httpx


async def analyze_screenshot_simple():
    """简单示例：只分析截图"""
    
    print("=" * 60)
    print("示例1: 只分析截图")
    print("=" * 60)
    
    # API配置
    server_url = "http://localhost:8000"
    parse_endpoint = f"{server_url}/api/v1/chat_screenshot/parse"
    
    # 构造请求（使用图片URL）
    request_data = {
        "image_url": "https://example.com/wechat_screenshot.png",
        "session_id": "demo-session-001",
        "options": {
            "need_nickname": True,
            "need_sender": True,
            "force_two_columns": True
        }
    }
    
    print(f"\n📤 发送请求到: {parse_endpoint}")
    print(f"   图片URL: {request_data['image_url']}")
    
    # 发送请求
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(parse_endpoint, json=request_data)
            response.raise_for_status()
            result = response.json()
            
            # 打印结果
            if result["code"] == 0:
                print("\n✅ 分析成功!")
                data = result["data"]
                
                # 打印参与者
                print(f"\n👥 参与者:")
                print(f"   自己: {data['participants']['self']['nickname']}")
                print(f"   对方: {data['participants']['other']['nickname']}")
                
                # 打印对话
                print(f"\n💬 对话内容 ({len(data['bubbles'])} 条):")
                for i, bubble in enumerate(data['bubbles'], 1):
                    sender = "我" if bubble['sender'] == 'user' else "对方"
                    print(f"   {i}. [{sender}] {bubble['text']}")
            else:
                print(f"\n❌ 分析失败: {result['msg']}")
                
        except httpx.HTTPError as e:
            print(f"\n❌ 请求失败: {e}")
            print("   提示: 请确保服务器正在运行 (python main.py)")


async def analyze_and_reply():
    """完整示例：分析截图 + 生成回复"""
    
    print("\n\n" + "=" * 60)
    print("示例2: 分析截图 + 生成回复")
    print("=" * 60)
    
    # API配置
    server_url = "http://localhost:8000"
    parse_endpoint = f"{server_url}/api/v1/chat_screenshot/parse"
    generate_endpoint = f"{server_url}/api/v1/generate_reply"
    
    # 步骤1: 分析截图
    print("\n📷 步骤1: 分析截图...")
    
    parse_request = {
        "image_url": "https://example.com/chat.png",
        "session_id": "demo-session-002",
        "options": {
            "need_nickname": True,
            "need_sender": True,
            "force_two_columns": True
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # 调用parse API
            response = await client.post(parse_endpoint, json=parse_request)
            response.raise_for_status()
            parse_result = response.json()
            
            if parse_result["code"] != 0:
                print(f"❌ 分析失败: {parse_result['msg']}")
                return
            
            print("✅ 分析成功!")
            data = parse_result["data"]
            
            # 步骤2: 转换为dialogs格式
            print("\n🔄 步骤2: 转换对话格式...")
            dialogs = []
            for bubble in data["bubbles"]:
                dialogs.append({
                    "speaker": bubble["sender"],
                    "text": bubble["text"],
                    "timestamp": None
                })
            print(f"   转换了 {len(dialogs)} 条消息")
            
            # 步骤3: 生成回复
            print("\n💬 步骤3: 生成回复...")
            
            generate_request = {
                "user_id": data["participants"]["self"]["id"],
                "target_id": data["participants"]["other"]["id"],
                "conversation_id": "conv-demo-002",
                "dialogs": dialogs,
                "intimacy_value": 50,
                "language": "zh-CN",
                "quality": "normal"
            }
            
            response = await client.post(generate_endpoint, json=generate_request)
            response.raise_for_status()
            reply_result = response.json()
            
            # 打印回复
            print("\n✅ 回复生成成功!")
            print(f"\n💬 生成的回复:")
            print(f"   {reply_result['reply_text']}")
            print(f"\n📊 元数据:")
            print(f"   模型: {reply_result['model']}")
            print(f"   成本: ${reply_result['cost_usd']:.4f}")
            
        except httpx.HTTPError as e:
            print(f"\n❌ 请求失败: {e}")


async def main():
    """运行所有示例"""
    
    print("\n🚀 Screenshot Analysis Client - 简单示例\n")
    
    # 示例1: 只分析
    await analyze_screenshot_simple()
    
    # 示例2: 分析 + 回复
    await analyze_and_reply()
    
    print("\n\n✅ 所有示例完成!")
    print("\n💡 提示:")
    print("   - 使用完整版客户端: python examples/screenshot_analysis_client.py --help")
    print("   - 启动服务器: python main.py")


if __name__ == "__main__":
    asyncio.run(main())
