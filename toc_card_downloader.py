"""
TOC 评级服务机构卡片图片下载器
基于抓包分析得到的 API 信息
"""

import requests
import json
import os
from pathlib import Path
from typing import List, Optional
import time
import random
import urllib3
import urllib.request
import urllib.error
import ssl

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 创建不验证SSL的context（用于urllib）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


class TOCCardDownloader:
    """TOC 卡片下载器"""
    
    def __init__(self, output_dir: str = "toc_cards"):
        """
        初始化下载器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # API 配置（从抓包分析得到）
        self.api_base_url = "https://tocpj.cn/index.php/api/cangka/getCardDetail"
        self.image_cdn = "https://qiniu.tocpj.cn"
        
        # 请求头（从抓包分析得到）
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541518) XWEB/17071",
            "Referer": "https://servicewechat.com/wx0f9c79ef318e0091/2/page-frame.html",
            "xweb_xhr": "1",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        # 禁用 SSL 验证（开发环境，生产环境应使用有效证书）
        self.session.verify = False
    
    def get_card_info(self, card_id: str) -> Optional[dict]:
        """
        获取卡片信息
        
        Args:
            card_id: 卡片ID（关键字）
            
        Returns:
            dict: 卡片信息，包含图片 URL
        """
        try:
            params = {"keyword": card_id}
            response = self.session.get(self.api_base_url, params=params, timeout=30, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 1:
                    return data.get('data')
                else:
                    print(f"  API 返回错误: {data.get('msg', '未知错误')}")
                    return None
            else:
                print(f"  请求失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  获取卡片信息时出错: {e}")
            return None
    
    def download_image(self, image_url: str, output_path: Path, max_retries: int = 3, use_urllib: bool = False) -> bool:
        """
        下载图片（带重试机制）
        
        Args:
            image_url: 图片 URL
            output_path: 输出路径
            max_retries: 最大重试次数
            use_urllib: 是否使用urllib而不是requests（备选方法）
            
        Returns:
            bool: 是否成功
        """
        # 从HAR文件中提取的完整请求头（关键：Accept包含image/wxpic）
        image_headers = {
            "Host": "qiniu.tocpj.cn",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541518) XWEB/17071",
            "Accept": "image/wxpic,image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",  # 关键：包含image/wxpic
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Dest": "image",
            "Referer": "https://servicewechat.com/wx0f9c79ef318e0091/2/page-frame.html",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        
        # 如果使用urllib方法
        if use_urllib:
            return self._download_image_urllib(image_url, output_path, image_headers, max_retries)
        
        # 使用requests方法
        for attempt in range(max_retries):
            try:
                # 创建新的session用于图片下载，避免影响API请求
                img_session = requests.Session()
                img_session.headers.update(image_headers)
                img_session.verify = False
                
                response = img_session.get(
                    image_url, 
                    timeout=60,  # 增加超时时间
                    stream=True
                )
                
                if response.status_code in [200, 206]:  # 200 OK 或 206 Partial Content
                    # 检查文件大小
                    content_length = response.headers.get('content-length')
                    total_size = int(content_length) if content_length else 0
                    
                    with open(output_path, 'wb') as f:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                    
                    # 验证文件是否下载完整（仅当有Content-Length时）
                    if total_size > 0 and downloaded < total_size:
                        print(f"  警告: 文件可能不完整 ({downloaded}/{total_size} 字节)")
                        if attempt < max_retries - 1:
                            print(f"  重试中... ({attempt + 1}/{max_retries})")
                            # 指数退避：2^attempt 秒 + 随机抖动
                            delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                            time.sleep(delay)
                            continue
                    
                    # 检查文件是否为空
                    if downloaded == 0:
                        print(f"  警告: 下载的文件为空")
                        if attempt < max_retries - 1:
                            print(f"  重试中... ({attempt + 1}/{max_retries})")
                            # 指数退避：2^attempt 秒 + 随机抖动
                            delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                            time.sleep(delay)
                            continue
                    
                    print(f"  ✓ 下载完成 ({downloaded} 字节)")
                    return True
                else:
                    error_text = response.text[:200] if hasattr(response, 'text') else ''
                    print(f"  下载失败，状态码: {response.status_code}")
                    if error_text:
                        print(f"  错误信息: {error_text}")
                    if attempt < max_retries - 1:
                        print(f"  重试中... ({attempt + 1}/{max_retries})")
                        # 指数退避：2^attempt 秒 + 随机抖动
                        delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                        time.sleep(delay)
                        continue
                    return False
                    
            except (ConnectionError, requests.exceptions.ConnectionError, requests.exceptions.RequestException, 
                    requests.exceptions.Timeout, requests.exceptions.SSLError) as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    print(f"  连接错误: {error_msg}")
                    print(f"  重试中... ({attempt + 1}/{max_retries})")
                    # 指数退避：2^attempt 秒 + 随机抖动
                    delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(delay)
                else:
                    print(f"  下载图片时出错: {error_msg}")
                    return False
            except Exception as e:
                print(f"  下载图片时出错: {e}")
                import traceback
                traceback.print_exc()
                if attempt < max_retries - 1:
                    # 指数退避：2^attempt 秒 + 随机抖动
                    delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(delay)
                    continue
                return False
        
        return False
    
    def _download_image_urllib(self, image_url: str, output_path: Path, headers: dict, max_retries: int = 3) -> bool:
        """
        使用urllib下载图片（备选方法）
        
        Args:
            image_url: 图片 URL
            output_path: 输出路径
            headers: 请求头
            max_retries: 最大重试次数
            
        Returns:
            bool: 是否成功
        """
        for attempt in range(max_retries):
            try:
                # 创建请求
                req = urllib.request.Request(image_url, headers=headers)
                
                # 使用不验证SSL的context
                with urllib.request.urlopen(req, timeout=60, context=ssl_context) as response:
                    # 检查状态码
                    status_code = response.getcode()
                    
                    if status_code in [200, 206]:  # 200 OK 或 206 Partial Content
                        # 读取内容
                        content = response.read()
                        
                        if len(content) > 0:
                            # 保存文件
                            with open(output_path, 'wb') as f:
                                f.write(content)
                            
                            print(f"  ✓ 下载完成 ({len(content)} 字节) [urllib]")
                            return True
                        else:
                            print(f"  警告: 下载的文件为空")
                            if attempt < max_retries - 1:
                                print(f"  重试中... ({attempt + 1}/{max_retries})")
                                # 指数退避：2^attempt 秒 + 随机抖动
                                delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                                time.sleep(delay)
                                continue
                    else:
                        print(f"  下载失败，状态码: {status_code}")
                        if attempt < max_retries - 1:
                            print(f"  重试中... ({attempt + 1}/{max_retries})")
                            # 指数退避：2^attempt 秒 + 随机抖动
                            delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                            time.sleep(delay)
                            continue
                        return False
                        
            except urllib.error.HTTPError as e:
                error_msg = f"HTTP错误 {e.code}: {e.reason}"
                if attempt < max_retries - 1:
                    print(f"  {error_msg}")
                    print(f"  重试中... ({attempt + 1}/{max_retries})")
                    # 指数退避：2^attempt 秒 + 随机抖动
                    delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(delay)
                else:
                    print(f"  下载图片时出错: {error_msg}")
                    return False
            except urllib.error.URLError as e:
                error_msg = f"URL错误: {e.reason}"
                if attempt < max_retries - 1:
                    print(f"  {error_msg}")
                    print(f"  重试中... ({attempt + 1}/{max_retries})")
                    # 指数退避：2^attempt 秒 + 随机抖动
                    delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(delay)
                else:
                    print(f"  下载图片时出错: {error_msg}")
                    return False
            except Exception as e:
                print(f"  下载图片时出错: {e}")
                if attempt < max_retries - 1:
                    # 指数退避：2^attempt 秒 + 随机抖动
                    delay = 2 * (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(delay)
                    continue
                return False
        
        return False
    
    def get_similar_cards_stats(self, name: str, detail: str) -> Optional[dict]:
        """
        获取相似卡片统计信息
        
        Args:
            name: 卡片名称
            detail: 卡片详情
            
        Returns:
            dict: 相似卡片统计信息
        """
        try:
            params = {
                "name": name,
                "detail": detail
            }
            response = self.session.get(
                "https://tocpj.cn/index.php/api/cangka/getSimilarCardsStats",
                params=params,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 1:
                    return data.get('data')
                else:
                    print(f"  API 返回错误: {data.get('msg', '未知错误')}")
                    return None
            else:
                print(f"  请求失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  获取相似卡片统计时出错: {e}")
            return None
    
    def download_card(self, card_id: str, save_info: bool = True) -> bool:
        """
        下载单个卡片
        
        Args:
            card_id: 卡片ID
            save_info: 是否保存卡片信息 JSON
            
        Returns:
            bool: 是否成功
        """
        print(f"\n正在处理卡片: {card_id}")
        
        # 获取卡片信息
        card_info = self.get_card_info(card_id)
        if not card_info:
            print(f"  ✗ 获取卡片信息失败")
            return False
        
        # 提取图片 URL
        image_url = card_info.get('images')
        if not image_url:
            print(f"  ✗ 未找到图片 URL")
            return False
        
        # 确定文件名
        card_name = card_info.get('name', card_id)
        rating_number = card_info.get('rating_number', card_id)
        
        # 下载主图片
        image_ext = Path(image_url).suffix or '.jpg'
        image_filename = f"{rating_number}_{card_name}{image_ext}".replace('/', '_').replace('\\', '_')
        image_path = self.output_dir / image_filename
        
        print(f"  图片URL: {image_url}")
        print(f"  保存到: {image_path}")
        
        # 先尝试使用requests
        success = self.download_image(image_url, image_path, use_urllib=False)
        
        # 如果失败，尝试使用urllib
        if not success:
            print(f"  ⚠ requests方法失败，尝试使用urllib...")
            success = self.download_image(image_url, image_path, use_urllib=True)
        
        if not success:
            print(f"  ✗ 图片下载失败")
            return False
        
        print(f"  ✓ 图片下载成功")
        
        # 对 TOC 卡片进行图片裁剪处理
        try:
            from card_image_processor import CardImageProcessor
            processor = CardImageProcessor()
            # 直接指定输出路径为原文件路径，保持原文件名和扩展名
            result = processor.process_image(image_path, output_path=image_path, save_debug=False)
            if result:
                print(f"  ✓ 图片裁剪处理完成")
        except Exception as e:
            print(f"  ⚠ 图片裁剪处理失败: {e}")
        
        # 保存卡片详情信息（只保存卡片详情，不包含额外统计）
        if save_info:
            info_filename = f"{rating_number}_info.json"
            info_path = self.output_dir / info_filename
            
            # 只保存卡片详情信息
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(card_info, f, ensure_ascii=False, indent=2)
            print(f"  ✓ 卡片详情已保存")
        
        return True
    
    def download_batch(self, card_ids: List[str], delay: float = 0.5) -> dict:
        """
        批量下载卡片
        
        Args:
            card_ids: 卡片ID列表
            delay: 请求间隔（秒）
            
        Returns:
            dict: 下载结果统计
        """
        print("=" * 60)
        print("批量下载 TOC 卡片")
        print("=" * 60)
        print(f"共 {len(card_ids)} 个卡片")
        print()
        
        results = {
            'success': 0,
            'failed': 0,
            'failed_ids': []
        }
        
        for i, card_id in enumerate(card_ids, 1):
            print(f"[{i}/{len(card_ids)}] ", end='')
            
            if self.download_card(card_id):
                results['success'] += 1
            else:
                results['failed'] += 1
                results['failed_ids'].append(card_id)
            
            # 延迟，避免请求过快
            if i < len(card_ids):
                time.sleep(delay)
        
        # 打印统计
        print("\n" + "=" * 60)
        print("下载完成")
        print("=" * 60)
        print(f"成功: {results['success']}/{len(card_ids)}")
        print(f"失败: {results['failed']}/{len(card_ids)}")
        if results['failed_ids']:
            print(f"失败的卡片ID: {', '.join(results['failed_ids'])}")
        print(f"\n文件保存在: {self.output_dir.absolute()}")
        
        return results


def main():
    """主函数"""
    print("=" * 60)
    print("TOC 评级服务机构卡片下载器")
    print("=" * 60)
    print()
    
    downloader = TOCCardDownloader()
    
    print("请选择操作:")
    print("1. 下载单个卡片")
    print("2. 批量下载卡片（从文件读取卡片ID列表）")
    print("3. 批量下载卡片（手动输入）")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    if choice == "1":
        card_id = input("请输入卡片ID: ").strip()
        downloader.download_card(card_id)
        
    elif choice == "2":
        file_path = input("请输入卡片ID列表文件路径（每行一个ID）: ").strip()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                card_ids = [line.strip() for line in f if line.strip()]
            
            if card_ids:
                downloader.download_batch(card_ids)
            else:
                print("文件为空")
        except Exception as e:
            print(f"读取文件时出错: {e}")
    
    elif choice == "3":
        print("请输入卡片ID（每行一个，输入空行结束）:")
        card_ids = []
        while True:
            card_id = input().strip()
            if not card_id:
                break
            card_ids.append(card_id)
        
        if card_ids:
            downloader.download_batch(card_ids)
        else:
            print("未输入任何卡片ID")
    
    else:
        print("无效的选择")


if __name__ == "__main__":
    main()
