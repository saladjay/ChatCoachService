#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Screenshot Analysis Client Example

这个示例展示如何调用第三方API完成screenshot analysis：
1. 输入本地图片路径
2. 上传图片到服务器
3. 调用screenshot parse API
4. 选择输出分析结果或继续走reply流程

使用方法:
    # 只分析截图
    python examples/screenshot_analysis_client.py --image path/to/screenshot.png --mode analyze
    
    # 分析截图并生成回复
    python examples/screenshot_analysis_client.py --image path/to/screenshot.png --mode reply
    
    # 指定服务器地址
    python examples/screenshot_analysis_client.py --image path/to/screenshot.png --mode reply --server http://localhost:8000
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Literal

import httpx


class ScreenshotAnalysisClient:
    """Screenshot分析客户端，用于调用第三方API"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        """初始化客户端
        
        Args:
            server_url: API服务器地址
        """
        self.server_url = server_url.rstrip("/")
        self.parse_endpoint = f"{self.server_url}/api/v1/chat_screenshot/parse"
        self.generate_endpoint = f"{self.server_url}/api/v1/generate_reply"
    
    async def upload_image(self, image_path: str) -> str:
        """上传图片到服务器（模拟）
        
        在实际应用中，你需要：
        1. 将图片上传到云存储（如S3, OSS等）
        2. 获取公开访问的URL
        3. 返回URL供API使用
        
        Args:
            image_path: 本地图片路径
            
        Returns:
            图片的公开访问URL
        """
        # 这里模拟上传过程
        # 实际应用中需要实现真实的上传逻辑
        print(f"📤 上传图片: {image_path}")
        
        # 检查文件是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 检查文件大小
        file_size = os.path.getsize(image_path)
        print(f"   文件大小: {file_size / 1024:.2f} KB")
        
        # TODO: 实际上传到云存储
        # 这里返回一个模拟的URL
        # 在生产环境中，你需要替换为真实的上传逻辑
        mock_url = f"https://example.com/uploads/{Path(image_path).name}"
        print(f"   ✓ 上传完成: {mock_url}")
        
        return mock_url
    
    async def analyze_screenshot(
        self,
        image_url: str,
        need_nickname: bool = True,
        need_sender: bool = True,
        force_two_columns: bool = True,
    ) -> dict:
        """调用API分析截图
        
        Args:
            image_url: 图片URL
            need_nickname: 是否需要提取昵称
            need_sender: 是否需要判断发送者
            force_two_columns: 是否强制两列布局
            
        Returns:
            API返回的分析结果
        """
        print(f"\n🔍 分析截图...")
        print(f"   图片URL: {image_url}")
        
        # 构造请求
        request_data = {
            "image_url": image_url,
            "session_id": f"client-{os.getpid()}",
            "options": {
                "need_nickname": need_nickname,
                "need_sender": need_sender,
                "force_two_columns": force_two_columns,
            }
        }
        
        # 发送请求
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.parse_endpoint,
                    json=request_data,
                )
                response.raise_for_status()
                result = response.json()
                
                # 检查返回码
                if result.get("code") != 0:
                    print(f"   ✗ 分析失败: {result.get('msg')}")
                    return result
                
                print(f"   ✓ 分析成功")
                return result
                
            except httpx.HTTPError as e:
                print(f"   ✗ 请求失败: {e}")
                raise
    
    async def generate_reply(
        self,
        parse_result: dict,
        intimacy_value: int = 50,
        language: str = "zh-CN",
        quality: Literal["cheap", "normal", "premium"] = "normal",
    ) -> dict:
        """基于分析结果生成回复
        
        Args:
            parse_result: screenshot分析结果
            intimacy_value: 亲密度值 (0-100)
            language: 回复语言
            quality: 生成质量
            
        Returns:
            生成的回复结果
        """
        print(f"\n💬 生成回复...")
        
        # 从分析结果中提取数据
        data = parse_result.get("data")
        if not data:
            raise ValueError("分析结果中没有数据")
        
        # 转换bubbles为dialogs格式
        dialogs = []
        for bubble in data.get("bubbles", []):
            dialogs.append({
                "speaker": bubble["sender"],
                "text": bubble["text"],
                "timestamp": None,
            })
        
        print(f"   对话消息数: {len(dialogs)}")
        
        # 构造生成请求
        participants = data.get("participants", {})
        request_data = {
            "user_id": participants.get("self", {}).get("id", "user_unknown"),
            "target_id": participants.get("other", {}).get("id", "target_unknown"),
            "conversation_id": f"conv-{os.getpid()}",
            "dialogs": dialogs,
            "intimacy_value": intimacy_value,
            "language": language,
            "quality": quality,
        }
        
        # 发送请求
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self.generate_endpoint,
                    json=request_data,
                )
                response.raise_for_status()
                result = response.json()
                
                print(f"   ✓ 回复生成成功")
                return result
                
            except httpx.HTTPError as e:
                print(f"   ✗ 请求失败: {e}")
                raise
    
    def print_analysis_result(self, result: dict):
        """打印分析结果
        
        Args:
            result: API返回的分析结果
        """
        print("\n" + "=" * 80)
        print("📊 分析结果")
        print("=" * 80)
        
        if result.get("code") != 0:
            print(f"❌ 错误: {result.get('msg')}")
            return
        
        data = result.get("data", {})
        
        # 图片信息
        image_meta = data.get("image_meta", {})
        print(f"\n📷 图片信息:")
        print(f"   尺寸: {image_meta.get('width')}x{image_meta.get('height')}")
        
        # 参与者信息
        participants = data.get("participants", {})
        print(f"\n👥 参与者:")
        self_info = participants.get("self", {})
        other_info = participants.get("other", {})
        print(f"   自己: {self_info.get('nickname')} (ID: {self_info.get('id')})")
        print(f"   对方: {other_info.get('nickname')} (ID: {other_info.get('id')})")
        
        # 布局信息
        layout = data.get("layout", {})
        print(f"\n📐 布局:")
        print(f"   类型: {layout.get('type')}")
        print(f"   左侧: {layout.get('left_role')}")
        print(f"   右侧: {layout.get('right_role')}")
        
        # 对话气泡
        bubbles = data.get("bubbles", [])
        print(f"\n💬 对话内容 ({len(bubbles)} 条消息):")
        for i, bubble in enumerate(bubbles, 1):
            sender_icon = "👤" if bubble["sender"] == "user" else "👥"
            confidence = bubble.get("confidence", 0) * 100
            print(f"\n   {i}. {sender_icon} {bubble['sender'].upper()}")
            print(f"      文本: {bubble['text']}")
            print(f"      位置: ({bubble['center_x']}, {bubble['center_y']})")
            print(f"      置信度: {confidence:.1f}%")
        
        print("\n" + "=" * 80)
    
    def print_reply_result(self, result: dict):
        """打印回复生成结果
        
        Args:
            result: API返回的回复结果
        """
        print("\n" + "=" * 80)
        print("💬 生成的回复")
        print("=" * 80)
        
        reply_text = result.get("reply_text", "")
        print(f"\n{reply_text}")
        
        print(f"\n📊 元数据:")
        print(f"   置信度: {result.get('confidence', 0):.2f}")
        print(f"   亲密度(前): {result.get('intimacy_level_before', 0)}")
        print(f"   亲密度(后): {result.get('intimacy_level_after', 0)}")
        print(f"   模型: {result.get('model', 'unknown')}")
        print(f"   提供商: {result.get('provider', 'unknown')}")
        print(f"   成本: ${result.get('cost_usd', 0):.4f}")
        print(f"   是否降级: {'是' if result.get('fallback') else '否'}")
        
        print("\n" + "=" * 80)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Screenshot Analysis Client - 调用第三方API分析聊天截图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 只分析截图
  python %(prog)s --image screenshot.png --mode analyze
  
  # 分析截图并生成回复
  python %(prog)s --image screenshot.png --mode reply
  
  # 指定应用类型
  python %(prog)s --image screenshot.png --mode analyze --app-type wechat
  
  # 指定服务器地址
  python %(prog)s --image screenshot.png --mode reply --server http://api.example.com
        """
    )
    
    # 必需参数
    parser.add_argument(
        "--image",
        required=True,
        help="本地图片路径"
    )
    
    parser.add_argument(
        "--mode",
        choices=["analyze", "reply"],
        default="analyze",
        help="运行模式: analyze=只分析, reply=分析+生成回复 (默认: analyze)"
    )
    
    # 可选参数
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="API服务器地址 (默认: http://localhost:8000)"
    )
    
    # parser.add_argument(
    #     "--app-type",
    #     choices=["wechat", "whatsapp", "line", "unknown"],
    #     default="unknown",
    #     help="聊天应用类型 (默认: unknown)"
    # )
    
    parser.add_argument(
        "--intimacy",
        type=int,
        default=50,
        help="亲密度值 0-100 (默认: 50)"
    )
    
    parser.add_argument(
        "--language",
        default="zh-CN",
        help="回复语言 (默认: zh-CN)"
    )
    
    parser.add_argument(
        "--quality",
        choices=["cheap", "normal", "premium"],
        default="normal",
        help="生成质量 (默认: normal)"
    )
    
    parser.add_argument(
        "--output",
        help="保存结果到JSON文件"
    )
    
    args = parser.parse_args()
    
    # 打印配置
    print("=" * 80)
    print("🚀 Screenshot Analysis Client")
    print("=" * 80)
    print(f"图片路径: {args.image}")
    print(f"运行模式: {args.mode}")
    print(f"服务器: {args.server}")
    # print(f"应用类型: {args.app_type}")
    if args.mode == "reply":
        print(f"亲密度: {args.intimacy}")
        print(f"语言: {args.language}")
        print(f"质量: {args.quality}")
    print("=" * 80)
    
    try:
        # 创建客户端
        client = ScreenshotAnalysisClient(server_url=args.server)
        
        # 步骤1: 上传图片
        image_url = await client.upload_image(args.image)
        
        # 步骤2: 分析截图
        analysis_result = await client.analyze_screenshot(
            image_url=image_url,
            # app_type=args.app_type,
        )
        
        # 打印分析结果
        client.print_analysis_result(analysis_result)
        
        # 保存分析结果
        results = {"analysis": analysis_result}
        
        # 步骤3: 如果是reply模式，继续生成回复
        if args.mode == "reply" and analysis_result.get("code") == 0:
            reply_result = await client.generate_reply(
                parse_result=analysis_result,
                intimacy_value=args.intimacy,
                language=args.language,
                quality=args.quality,
            )
            
            # 打印回复结果
            client.print_reply_result(reply_result)
            
            # 保存回复结果
            results["reply"] = reply_result
        
        # 保存到文件
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 结果已保存到: {args.output}")
        
        print("\n✅ 完成!")
        
    except FileNotFoundError as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"\n❌ 网络错误: {e}")
        print(f"   请确保服务器 {args.server} 正在运行")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
