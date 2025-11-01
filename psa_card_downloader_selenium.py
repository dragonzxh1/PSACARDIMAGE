"""
PSA卡片高清图片下载爬虫（Selenium版本）
适用于需要JavaScript渲染的页面
需要安装: pip install selenium beautifulsoup4
需要下载ChromeDriver: https://chromedriver.chromium.org/
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
import re
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse
import time
from typing import List, Optional, Tuple


class PSACardImageDownloaderSelenium:
    """PSA卡片高清图片下载器（使用Selenium）"""
    
    def __init__(self, base_url: str = "https://www.psacard.com/cert", headless: bool = True):
        """
        初始化下载器
        
        Args:
            base_url: PSA证书验证页面的基础URL
            headless: 是否使用无头模式
        """
        self.base_url = base_url.rstrip('/')
        self.headless = headless
        self.driver = None
        self._init_driver()
        
    def _init_driver(self):
        """初始化Selenium WebDriver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
        except Exception as e:
            raise Exception(f"无法初始化Chrome浏览器。请确保已安装Chrome和ChromeDriver。\n错误: {str(e)}")
    
    def __del__(self):
        """清理资源"""
        if self.driver:
            self.driver.quit()
    
    def _extract_cert_number(self, cert_input: str) -> str:
        """从用户输入中提取纯数字证书编号"""
        cert_number = re.sub(r'\D', '', cert_input)
        if not cert_number:
            raise ValueError(f"无法从输入 '{cert_input}' 中提取有效的证书编号")
        return cert_number
    
    def _get_page_with_selenium(self, cert_number: str) -> Tuple[str, BeautifulSoup]:
        """
        使用Selenium获取完全渲染后的页面
        
        Args:
            cert_number: PSA证书编号
            
        Returns:
            (页面HTML, BeautifulSoup对象)
        """
        url = f"{self.base_url}/{cert_number}"
        print(f"正在访问: {url}")
        
        try:
            self.driver.get(url)
            # 等待页面加载
            time.sleep(3)
            
            # 等待图片元素加载（最多等待10秒）
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "img"))
                )
            except:
                pass  # 如果超时也继续，可能图片已经在HTML中
            
            # 获取完全渲染后的HTML
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            return html, soup
            
        except Exception as e:
            raise Exception(f"无法访问页面: {url}\n错误: {str(e)}")
    
    def _find_image_urls(self, soup: BeautifulSoup) -> List[str]:
        """从BeautifulSoup对象中提取高清图片URL"""
        image_urls = []
        
        # 方法1: 查找所有img标签
        img_tags = soup.find_all('img')
        for img in img_tags:
            for attr in ['src', 'data-src', 'data-highres', 'data-original', 'data-large', 'data-lazy']:
                url = img.get(attr)
                if url:
                    full_url = urljoin(self.base_url, url)
                    if self._is_high_res_image(full_url):
                        if full_url not in image_urls:
                            image_urls.append(full_url)
        
        # 方法2: 使用Selenium查找动态加载的图片
        try:
            selenium_imgs = self.driver.find_elements(By.TAG_NAME, "img")
            for img in selenium_imgs:
                for attr in ['src', 'data-src', 'data-highres']:
                    try:
                        url = img.get_attribute(attr)
                        if url:
                            full_url = urljoin(self.base_url, url)
                            if self._is_high_res_image(full_url):
                                if full_url not in image_urls:
                                    image_urls.append(full_url)
                    except:
                        continue
        except:
            pass
        
        # 方法3: 查找网络请求中的图片URL（通过执行JavaScript获取）
        try:
            # 执行JavaScript获取所有图片URL
            js_code = """
            var images = [];
            var imgs = document.getElementsByTagName('img');
            for(var i=0; i<imgs.length; i++) {
                var src = imgs[i].src || imgs[i].getAttribute('data-src') || imgs[i].getAttribute('data-highres');
                if(src && src.indexOf('http') !== -1) {
                    images.push(src);
                }
            }
            return images;
            """
            js_images = self.driver.execute_script(js_code)
            for url in js_images:
                if self._is_high_res_image(url):
                    if url not in image_urls:
                        image_urls.append(url)
        except:
            pass
        
        return image_urls[:2]  # 只返回前两张
        
    def _is_high_res_image(self, url: str) -> bool:
        """判断URL是否可能是高清图片"""
        if not url:
            return False
            
        url_lower = url.lower()
        
        # 排除
        exclude_keywords = ['logo', 'icon', 'avatar', 'button', 'badge', 'flag', 'spinner', 'loading']
        if any(keyword in url_lower for keyword in exclude_keywords):
            return False
        
        # 必须是图片格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if not any(ext in url_lower for ext in image_extensions):
            return False
        
        # 优先选择高清图
        high_res_keywords = ['highres', 'high-res', 'high_res', 'large', 'original', 'full', 
                           'hd', 'high', 'big', 'max', 'cert']
        if any(keyword in url_lower for keyword in high_res_keywords):
            return True
        
        # PSA相关的图片路径
        if '/cert/' in url_lower or 'card' in url_lower or 'image' in url_lower:
            return True
        
        return False
    
    def get_high_res_images(self, cert_number: str) -> Tuple[List[str], str]:
        """获取指定证书编号的高清图片URL列表"""
        cert_num = self._extract_cert_number(cert_number)
        html, soup = self._get_page_with_selenium(cert_num)
        
        # 提取标题
        title_tag = soup.find('title')
        page_title = title_tag.text.strip() if title_tag else f"PSA Certificate {cert_num}"
        
        # 查找图片
        image_urls = self._find_image_urls(soup)
        
        return image_urls, page_title
    
    def download_image(self, url: str, save_path: Path, filename: str = None) -> bool:
        """下载单张图片"""
        try:
            print(f"正在下载: {url}")
            
            # 使用requests下载（比Selenium更高效）
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            response = session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            if not filename:
                parsed_url = urlparse(url)
                filename = os.path.basename(parsed_url.path)
                if not filename or '.' not in filename:
                    filename = f"image_{int(time.time())}.jpg"
            
            save_path.mkdir(parents=True, exist_ok=True)
            file_path = save_path / filename
            
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r进度: {progress:.1f}%", end='', flush=True)
            
            print(f"\n✓ 已保存: {file_path}")
            print(f"  文件大小: {downloaded / 1024:.2f} KB")
            return True
            
        except Exception as e:
            print(f"\n✗ 下载失败: {url}\n  错误: {str(e)}")
            return False
    
    def download_images(self, cert_number: str, save_dir: str = "downloads") -> bool:
        """下载指定证书编号的所有高清图片"""
        try:
            image_urls, page_title = self.get_high_res_images(cert_number)
            
            if not image_urls:
                print(f"错误: 未能找到证书编号 {cert_number} 的图片")
                return False
            
            print(f"\n找到 {len(image_urls)} 张图片:")
            for i, url in enumerate(image_urls, 1):
                print(f"  {i}. {url}")
            
            cert_num = self._extract_cert_number(cert_number)
            save_path = Path(save_dir) / f"PSA_{cert_num}"
            
            success_count = 0
            for i, url in enumerate(image_urls, 1):
                filename = f"image_{i}_{os.path.basename(urlparse(url).path)}"
                if '.' not in filename:
                    filename += '.jpg'
                
                if self.download_image(url, save_path, filename):
                    success_count += 1
                print()
            
            if success_count > 0:
                print(f"\n✓ 成功下载 {success_count}/{len(image_urls)} 张图片")
                print(f"保存位置: {save_path.absolute()}")
                return True
            else:
                print("\n✗ 所有图片下载失败")
                return False
                
        except Exception as e:
            print(f"\n✗ 下载过程出错: {str(e)}")
            return False
        finally:
            if self.driver:
                self.driver.quit()


def main():
    """主程序入口"""
    print("=" * 60)
    print("PSA卡片高清图片下载器（Selenium版本）")
    print("=" * 60)
    print()
    
    try:
        downloader = PSACardImageDownloaderSelenium(headless=True)
        
        while True:
            try:
                cert_input = input("请输入PSA证书编号（输入 'q' 退出）: ").strip()
                
                if cert_input.lower() == 'q':
                    print("再见！")
                    break
                
                if not cert_input:
                    print("请输入有效的证书编号")
                    continue
                
                print("\n开始处理...")
                downloader.download_images(cert_input)
                print("\n" + "=" * 60 + "\n")
                
            except KeyboardInterrupt:
                print("\n\n程序已中断")
                break
            except Exception as e:
                print(f"\n错误: {str(e)}\n")
                
    except Exception as e:
        print(f"初始化失败: {str(e)}")
        print("\n请确保:")
        print("1. 已安装Chrome浏览器")
        print("2. 已下载并配置ChromeDriver")
        print("3. 或使用普通版本: python psa_card_downloader.py")


if __name__ == "__main__":
    main()

