#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Screenshot Analysis 完整流程演示

这个脚本演示了从本地图片到生成回复的完整流程，使用mock数据模拟API调用。
可以在没有运行服务器的情况下查看完整流程。

使用方法:
    python examples/demo_screenshot_flow.py
"""

import asyncio
import json
from typing import Literal


class MockScreenshotClient:
    """模拟的Screenshot客户端，用于演示流程"""
    
    def __init__(self):
        self.session_count = 0
    
    async def upload_image(self, image_path: str) -> str:
        """模拟上传图片"""
        print(f"\n📤 步骤1: 上传图片")
        print(f"   本地路径: {image_path}")
        
        # 模拟上传延迟
        await asyncio.sleep(0.5)
        
        # 返回模拟URL
        mock_url = f"https://cdn.example.com/screenshots/{image_path.split('/')[-1]}"
        print(f"   ✓ 上传成功")
        print(f"   图片URL: {mock_url}")
        
        return mock_url
    
    async def analyze_screenshot(
        self,
        image_url: str
    ) -> dict:
        """模拟分析截图"""
        print(f"\n🔍 步骤2: 分析截图")
        print(f"   图片URL: {image_url}")
        
        # 模拟API调用延迟
        await asyncio.sleep(1.0)
        
        # 返回模拟的分析结果
        result = {
            "code": 0,
            "msg": "Success",
            "data": {
                "image_meta": {
                    "width": 750,
                    "height": 1334
                },
                "participants": {
                    "self": {
                        "id": "user_wechat_123",
                        "nickname": "我"
                    },
                    "other": {
                        "id": "friend_wechat_456",
                        "nickname": "小明"
                    }
                },
                "bubbles": [
                    {
                        "bubble_id": "b1",
                        "bbox": {"x1": 400, "y1": 100, "x2": 700, "y2": 160},
                        "center_x": 550,
                        "center_y": 130,
                        "text": "嗨！周末有空吗？",
                        "sender": "user",
                        "column": "right",
                        "confidence": 0.95
                    },
                    {
                        "bubble_id": "b2",
                        "bbox": {"x1": 50, "y1": 180, "x2": 350, "y2": 240},
                        "center_x": 200,
                        "center_y": 210,
                        "text": "有啊，怎么了？",
                        "sender": "talker",
                        "column": "left",
                        "confidence": 0.92
                    },
                    {
                        "bubble_id": "b3",
                        "bbox": {"x1": 400, "y1": 260, "x2": 700, "y2": 340},
                        "center_x": 550,
                        "center_y": 300,
                        "text": "想约你一起去看电影，有部新片很不错",
                        "sender": "user",
                        "column": "right",
                        "confidence": 0.88
                    },
                    {
                        "bubble_id": "b4",
                        "bbox": {"x1": 50, "y1": 360, "x2": 350, "y2": 420},
                        "center_x": 200,
                        "center_y": 390,
                        "text": "好啊！什么电影？",
                        "sender": "talker",
                        "column": "left",
                        "confidence": 0.90
                    }
                ],
                "layout": {
                    "type": "two_columns",
                    "left_role": "talker",
                    "right_role": "user"
                }
            }
        }
        
        print(f"   ✓ 分析完成")
        print(f"   识别到 {len(result['data']['bubbles'])} 条消息")
        
        return result
    
    def convert_to_dialogs(self, parse_result: dict) -> list[dict]:
        """转换为dialogs格式"""
        print(f"\n🔄 步骤3: 转换对话格式")
        
        data = parse_result["data"]
        dialogs = []
        
        for bubble in data["bubbles"]:
            dialogs.append({
                "speaker": bubble["sender"],
                "text": bubble["text"],
                "timestamp": None
            })
        
        print(f"   ✓ 转换完成")
        print(f"   对话消息数: {len(dialogs)}")
        
        return dialogs
    
    async def generate_reply(
        self,
        dialogs: list[dict],
        user_id: str,
        target_id: str,
        intimacy_value: int = 50,
        language: str = "zh-CN"
    ) -> dict:
        """模拟生成回复"""
        print(f"\n💬 步骤4: 生成回复")
        print(f"   用户ID: {user_id}")
        print(f"   目标ID: {target_id}")
        print(f"   亲密度: {intimacy_value}")
        print(f"   语言: {language}")
        print(f"   对话长度: {len(dialogs)} 条")
        
        # 模拟API调用延迟
        await asyncio.sleep(1.5)
        
        # 返回模拟的回复结果
        result = {
            "reply_text": "《流浪地球3》！我也想看这部，听说特效很震撼。周六下午怎么样？",
            "confidence": 0.87,
            "intimacy_level_before": 3,
            "intimacy_level_after": 3,
            "model": "qwen-plus",
            "provider": "dashscope",
            "cost_usd": 0.0025,
            "fallback": False
        }
        
        print(f"   ✓ 回复生成完成")
        
        return result
    
    def print_analysis_result(self, result: dict):
        """打印分析结果"""
        print("\n" + "=" * 80)
        print("📊 分析结果详情")
        print("=" * 80)
        
        data = result["data"]
        
        # 图片信息
        image_meta = data["image_meta"]
        print(f"\n📷 图片信息:")
        print(f"   尺寸: {image_meta['width']}x{image_meta['height']}")
        
        # 参与者
        participants = data["participants"]
        print(f"\n👥 参与者:")
        print(f"   自己: {participants['self']['nickname']} (ID: {participants['self']['id']})")
        print(f"   对方: {participants['other']['nickname']} (ID: {participants['other']['id']})")
        
        # 布局
        layout = data["layout"]
        print(f"\n📐 布局:")
        print(f"   类型: {layout['type']}")
        print(f"   左侧角色: {layout['left_role']}")
        print(f"   右侧角色: {layout['right_role']}")
        
        # 对话内容
        bubbles = data["bubbles"]
        print(f"\n💬 对话内容 ({len(bubbles)} 条消息):")
        for i, bubble in enumerate(bubbles, 1):
            sender_icon = "👤" if bubble["sender"] == "user" else "👥"
            sender_name = "我" if bubble["sender"] == "user" else "对方"
            confidence = bubble["confidence"] * 100
            
            print(f"\n   消息 {i}:")
            print(f"   {sender_icon} {sender_name}")
            print(f"   内容: {bubble['text']}")
            print(f"   位置: ({bubble['center_x']}, {bubble['center_y']})")
            print(f"   置信度: {confidence:.1f}%")
        
        print("\n" + "=" * 80)
    
    def print_reply_result(self, result: dict):
        """打印回复结果"""
        print("\n" + "=" * 80)
        print("💬 生成的回复")
        print("=" * 80)
        
        print(f"\n📝 回复内容:")
        print(f"   {result['reply_text']}")
        
        print(f"\n📊 生成元数据:")
        print(f"   置信度: {result['confidence']:.2f}")
        print(f"   亲密度(前): {result['intimacy_level_before']}")
        print(f"   亲密度(后): {result['intimacy_level_after']}")
        print(f"   使用模型: {result['model']}")
        print(f"   提供商: {result['provider']}")
        print(f"   成本: ${result['cost_usd']:.4f}")
        print(f"   是否降级: {'是' if result['fallback'] else '否'}")
        
        print("\n" + "=" * 80)


async def demo_analyze_only():
    """演示：只分析截图"""
    print("\n" + "=" * 80)
    print("🎬 演示场景1: 只分析截图")
    print("=" * 80)
    
    client = MockScreenshotClient()
    
    # 模拟本地图片路径
    image_path = "screenshots/wechat_chat_001.png"
    
    # 步骤1: 上传图片
    image_url = await client.upload_image(image_path)
    
    # 步骤2: 分析截图
    analysis_result = await client.analyze_screenshot(
        image_url=image_url
    )
    
    # 打印详细结果
    client.print_analysis_result(analysis_result)
    
    print("\n✅ 场景1完成: 截图分析成功")


async def demo_analyze_and_reply():
    """演示：分析截图 + 生成回复"""
    print("\n\n" + "=" * 80)
    print("🎬 演示场景2: 分析截图 + 生成回复")
    print("=" * 80)
    
    client = MockScreenshotClient()
    
    # 模拟本地图片路径
    image_path = "screenshots/wechat_chat_002.png"
    
    # 步骤1: 上传图片
    image_url = await client.upload_image(image_path)
    
    # 步骤2: 分析截图
    analysis_result = await client.analyze_screenshot(
        image_url=image_url
    )
    
    # 打印分析结果
    client.print_analysis_result(analysis_result)
    
    # 步骤3: 转换为dialogs格式
    dialogs = client.convert_to_dialogs(analysis_result)
    
    # 步骤4: 生成回复
    data = analysis_result["data"]
    reply_result = await client.generate_reply(
        dialogs=dialogs,
        user_id=data["participants"]["self"]["id"],
        target_id=data["participants"]["other"]["id"],
        intimacy_value=60,
        language="zh-CN"
    )
    
    # 打印回复结果
    client.print_reply_result(reply_result)
    
    print("\n✅ 场景2完成: 截图分析 + 回复生成成功")


async def demo_different_apps():
    """演示：不同聊天应用"""
    print("\n\n" + "=" * 80)
    print("🎬 演示场景3: 不同聊天应用")
    print("=" * 80)
    
    client = MockScreenshotClient()
    
    apps = [
        ("WeChat", "screenshots/wechat.png"),
        ("WhatsApp", "screenshots/whatsapp.png"),
        ("LINE", "screenshots/line.png"),
    ]
    
    for app_name, image_path in apps:
        print(f"\n📱 测试 {app_name}...")
        
        # 上传和分析
        image_url = await client.upload_image(image_path)
        result = await client.analyze_screenshot(image_url)
        
        # 简要输出
        if result["code"] == 0:
            bubble_count = len(result["data"]["bubbles"])
            print(f"   ✓ 成功识别 {bubble_count} 条消息")
        else:
            print(f"   ✗ 分析失败: {result['msg']}")
    
    print("\n✅ 场景3完成: 多应用测试完成")


async def demo_error_handling():
    """演示：错误处理"""
    print("\n\n" + "=" * 80)
    print("🎬 演示场景4: 错误处理")
    print("=" * 80)
    
    print("\n📝 常见错误场景:")
    
    errors = [
        {
            "code": 1001,
            "msg": "Failed to download image from URL",
            "scenario": "图片URL无效或无法访问"
        },
        {
            "code": 1002,
            "msg": "LLM API call failed",
            "scenario": "LLM服务调用失败"
        },
        {
            "code": 1003,
            "msg": "Failed to parse JSON from LLM response",
            "scenario": "LLM返回格式错误"
        },
        {
            "code": 1004,
            "msg": "Missing or invalid required fields in LLM output",
            "scenario": "LLM输出缺少必需字段"
        }
    ]
    
    for error in errors:
        print(f"\n   错误码 {error['code']}:")
        print(f"   场景: {error['scenario']}")
        print(f"   消息: {error['msg']}")
        print(f"   处理: 检查输入并重试")
    
    print("\n✅ 场景4完成: 错误处理说明")


async def main():
    """运行所有演示"""
    print("\n" + "=" * 80)
    print("🚀 Screenshot Analysis 完整流程演示")
    print("=" * 80)
    print("\n这个演示展示了从本地图片到生成回复的完整流程")
    print("使用mock数据模拟API调用，无需启动服务器")
    print("\n" + "=" * 80)
    
    # 场景1: 只分析
    await demo_analyze_only()
    
    # 场景2: 分析 + 回复
    await demo_analyze_and_reply()
    
    # 场景3: 不同应用
    await demo_different_apps()
    
    # 场景4: 错误处理
    await demo_error_handling()
    
    # 总结
    print("\n\n" + "=" * 80)
    print("🎉 所有演示完成!")
    print("=" * 80)
    
    print("\n📚 下一步:")
    print("   1. 查看完整客户端: examples/screenshot_analysis_client.py")
    print("   2. 查看简单示例: examples/simple_screenshot_client.py")
    print("   3. 阅读使用文档: examples/SCREENSHOT_CLIENT_USAGE.md")
    print("   4. 启动真实服务器: python main.py")
    
    print("\n💡 提示:")
    print("   - 这个演示使用mock数据，实际使用需要启动API服务器")
    print("   - 生产环境需要实现真实的图片上传逻辑")
    print("   - 建议使用云存储服务（如S3, OSS）存储图片")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
