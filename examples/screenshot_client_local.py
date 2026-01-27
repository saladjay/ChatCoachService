#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Screenshot Analysis Client - Local File Version

这个版本支持本地文件，通过启动临时HTTP服务器来提供图片访问。

使用方法:
    python examples/screenshot_client_local.py --image path/to/screenshot.png --mode analyze
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import socket

import httpx


def find_free_port():
    """找到一个可用的端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    """安静的HTTP请求处理器，不打印日志"""
    def log_message(self, format, *args):
        pass


class LocalFileServer:
    """本地文件服务器，用于临时提供图片访问"""
    
    def __init__(self, directory: str):
        self.directory = Path(directory).resolve()
        self.port = find_free_port()
        self.server = None
        self.thread = None
        
    def start(self):
        """启动服务器"""
        os.chdir(self.directory)
        self.server = HTTPServer(('127.0.0.1', self.port), QuietHTTPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"📁 启动本地文件服务器: http://127.0.0.1:{self.port}")
        
    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            print(f"🛑 停止本地文件服务器")
    
    def get_url(self, filename: str) -> str:
        """获取文件的URL"""
        return f"http://127.0.0.1:{self.port}/{filename}"


class ScreenshotAnalysisClient:
    """Screenshot分析客户端"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip("/")
        self.parse_endpoint = f"{self.server_url}/api/v1/chat_screenshot/parse"
        self.generate_endpoint = f"{self.server_url}/api/v1/generate_reply"
        self.file_server = None
    
    def setup_local_file_server(self, image_path: str) -> str:
        """设置本地文件服务器并返回图片URL
        
        Args:
            image_path: 本地图片路径
            
        Returns:
            图片的本地访问URL
        """
        image_path = Path(image_path).resolve()
        
        if not image_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        print(f"📤 准备图片: {image_path}")
        file_size = image_path.stat().st_size
        print(f"   文件大小: {file_size / 1024:.2f} KB")
        
        # 启动本地文件服务器
        self.file_server = LocalFileServer(image_path.parent)
        self.file_server.start()
        
        # 获取图片URL
        image_url = self.file_server.get_url(image_path.name)
        print(f"   ✓ 图片URL: {image_url}")
        
        return image_url
    
    def cleanup(self):
        """清理资源"""
        if self.file_server:
            self.file_server.stop()
    
    async def analyze_screenshot(
        self,
        image_url: str,
        session_id: str = "test-session",
    ) -> dict:
        """调用API分析截图
        
        Args:
            image_url: 图片URL
            session_id: 会话ID
            
        Returns:
            API返回的分析结果
        """
        print(f"\n🔍 分析截图...")
        print(f"   API端点: {self.parse_endpoint}")
        
        request_data = {
            "image_url": image_url,
            "session_id": session_id,
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.parse_endpoint,
                    json=request_data
                )
                
                if response.status_code != 200:
                    print(f"   ✗ HTTP错误: {response.status_code}")
                    return {"error": f"HTTP {response.status_code}", "detail": response.text}
                
                result = response.json()
                
                if result.get("code") == 0:
                    print(f"   ✓ 分析成功!")
                else:
                    print(f"   ✗ 分析失败: {result.get('msg', 'Unknown error')}")
                
                return result
                
        except httpx.RequestError as e:
            print(f"   ✗ 请求失败: {e}")
            return {"error": "request_failed", "detail": str(e)}
        except Exception as e:
            print(f"   ✗ 未知错误: {e}")
            return {"error": "unknown", "detail": str(e)}
    
    async def generate_reply(
        self,
        parsed_data: dict,
        user_id: str = "test_user",
        intimacy_level: str = "acquaintance",
        language: str = "zh",
    ) -> dict:
        """调用API生成回复
        
        Args:
            parsed_data: 解析后的截图数据
            user_id: 用户ID
            intimacy_level: 亲密度级别
            language: 语言
            
        Returns:
            API返回的生成结果
        """
        print(f"\n💬 生成回复...")
        
        # 从parsed_data构建GenerateReplyRequest
        request_data = {
            "user_id": user_id,
            "conversation_history": parsed_data.get("bubbles", []),
            "intimacy_level": intimacy_level,
            "language": language,
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.generate_endpoint,
                    json=request_data
                )
                
                if response.status_code != 200:
                    print(f"   ✗ HTTP错误: {response.status_code}")
                    return {"error": f"HTTP {response.status_code}", "detail": response.text}
                
                result = response.json()
                print(f"   ✓ 生成成功!")
                return result
                
        except httpx.RequestError as e:
            print(f"   ✗ 请求失败: {e}")
            return {"error": "request_failed", "detail": str(e)}
        except Exception as e:
            print(f"   ✗ 未知错误: {e}")
            return {"error": "unknown", "detail": str(e)}


def print_banner():
    """打印横幅"""
    print("=" * 80)
    print("🚀 Screenshot Analysis Client (Local File Version)")
    print("=" * 80)


def print_result(result: dict, mode: str):
    """打印结果"""
    print("\n" + "=" * 80)
    print("📊 结果")
    print("=" * 80)
    
    if mode == "analyze":
        if result.get("code") == 0:
            data = result.get("data", {})
            print(f"\n✅ 分析成功!")
            print(f"\n应用类型: {data.get('app_type', 'unknown')}")
            print(f"布局: {data.get('layout', 'unknown')}")
            
            bubbles = data.get("bubbles", [])
            print(f"\n对话气泡数量: {len(bubbles)}")
            
            if bubbles:
                print("\n对话内容:")
                for i, bubble in enumerate(bubbles[:5], 1):  # 只显示前5条
                    print(f"\n  [{i}] {bubble.get('sender', 'unknown')}")
                    print(f"      文本: {bubble.get('text', '')[:100]}")
                    print(f"      置信度: {bubble.get('confidence', 0):.2f}")
                    print(f"      位置: ({bubble.get('center_x', 0)}, {bubble.get('center_y', 0)})")
                
                if len(bubbles) > 5:
                    print(f"\n  ... 还有 {len(bubbles) - 5} 条对话")
            
            participants = data.get("participants", {})
            if participants:
                # participants可能是字典（包含self和other）或列表
                if isinstance(participants, dict):
                    names = []
                    if "self" in participants:
                        names.append(participants["self"].get("nickname", "unknown"))
                    if "other" in participants:
                        names.append(participants["other"].get("nickname", "unknown"))
                    if names:
                        print(f"\n参与者: {', '.join(names)}")
                elif isinstance(participants, list):
                    print(f"\n参与者: {', '.join([p.get('name', 'unknown') for p in participants])}")
        else:
            print(f"\n❌ 错误 (代码 {result.get('code')}): {result.get('msg', 'Unknown error')}")
    
    elif mode == "reply":
        if "reply" in result:
            print(f"\n✅ 生成的回复:\n{result['reply']}")
        else:
            print(f"\n❌ 错误: {result.get('error', 'Unknown error')}")
    
    print("\n完整响应:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Screenshot Analysis Client (Local File Version)")
    parser.add_argument("--image", required=True, help="本地图片路径")
    parser.add_argument("--mode", choices=["analyze", "reply"], default="analyze",
                       help="运行模式: analyze=只分析, reply=分析+生成回复")
    parser.add_argument("--server", default="http://localhost:8000",
                       help="API服务器地址")
    parser.add_argument("--session-id", default="test-session",
                       help="会话ID")
    
    args = parser.parse_args()
    
    print_banner()
    print(f"图片路径: {args.image}")
    print(f"运行模式: {args.mode}")
    print(f"服务器: {args.server}")
    print("=" * 80)
    
    client = ScreenshotAnalysisClient(server_url=args.server)
    
    try:
        # 设置本地文件服务器
        image_url = client.setup_local_file_server(args.image)
        
        # 分析截图
        result = await client.analyze_screenshot(
            image_url=image_url,
            session_id=args.session_id,
        )
        
        # 如果是reply模式且分析成功，继续生成回复
        if args.mode == "reply" and result.get("code") == 0:
            parsed_data = result.get("data", {})
            reply_result = await client.generate_reply(parsed_data)
            result = reply_result
        
        # 打印结果
        print_result(result, args.mode)
        
    except FileNotFoundError as e:
        print(f"\n❌ 文件错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 清理资源
        client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
