"""
PSA卡片高清图片下载爬虫
支持根据PSA证书编号下载对应卡片的高清图片
"""

import requests
from bs4 import BeautifulSoup
import re
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse
import time
from typing import List, Optional, Tuple, Dict
import urllib3
import random
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from psa_item_info_extractor import PSAItemInfoExtractor

# 禁用SSL警告（因为我们可能禁用SSL验证）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PSACardImageDownloader:
    """PSA卡片高清图片下载器"""
    
    def __init__(self, base_url: str = "https://www.psacard.com/cert", verify_ssl: bool = False):
        """
        初始化下载器
        
        Args:
            base_url: PSA证书验证页面的基础URL（主URL）
            verify_ssl: 是否验证SSL证书（默认False，避免证书验证错误）
        """
        self.base_url = base_url.rstrip('/')
        # 备选URL列表（如果主URL失败，会尝试这些）
        self.backup_urls = [
            "https://www.psacard.co.jp/cert",
            "https://www.psacard.com/cert"
        ]
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        # 禁用SSL验证（如果verify_ssl为False）
        self.session.verify = verify_ssl
        # 设置请求头，模拟浏览器
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.max_retries = 3
        self.retry_delay = 1  # 秒
        # 防封与节流
        self.min_request_interval = 0.6
        self._last_request_ts = 0.0
        self._user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        ]
        self._proxy_pool = [p.strip() for p in os.getenv("PSA_PROXIES", "").split(",") if p.strip()]
        self._current_proxies: Optional[Dict[str, str]] = None
        # 安装 requests 重试适配器
        retry_config = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_config, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        # 随机化首个 UA
        self.session.headers["User-Agent"] = random.choice(self._user_agents)
        
    def _extract_cert_number(self, cert_input: str) -> str:
        """
        从用户输入中提取纯数字证书编号
        
        Args:
            cert_input: 用户输入的证书编号（可能包含PSA前缀等）
            
        Returns:
            纯数字的证书编号
        """
        # 移除所有非数字字符，保留数字
        cert_number = re.sub(r'\D', '', cert_input)
        if not cert_number:
            raise ValueError(f"无法从输入 '{cert_input}' 中提取有效的证书编号")
        return cert_number
    
    def _get_page_html(self, cert_number: str) -> str:
        """
        获取证书页面的HTML内容
        如果主URL失败，会自动尝试备选URL（psacard.co.jp等）
        
        Args:
            cert_number: PSA证书编号
            
        Returns:
            页面HTML内容
            
        Raises:
            requests.RequestException: 当所有URL都失败时
        """
        # 构建要尝试的URL列表（优先使用主URL，然后是备选URL）
        urls_to_try = [self.base_url] + [url for url in self.backup_urls if url != self.base_url]
        
        last_error = None
        tried_without_proxy = False  # 标记是否已尝试不使用代理
        
        for base_url in urls_to_try:
            # 对于psacard.com，尝试两种URL格式：
            # 1. /cert/{编号} (标准格式)
            # 2. /cert/{编号}/psa (英文网站格式)
            if 'psacard.com' in base_url and 'psacard.co.jp' not in base_url:
                urls = [
                    f"{base_url}/{cert_number}",
                    f"{base_url}/{cert_number}/psa"
                ]
            else:
                urls = [f"{base_url}/{cert_number}"]
            
            for url in urls:
                print(f"正在访问: {url}")
                
                for attempt in range(self.max_retries):
                    try:
                        self._throttle()
                        if attempt > 0:
                            self._maybe_rotate_identity()
                        # 如果之前代理失败过，这次就不使用代理
                        proxies_to_use = None if tried_without_proxy else self._current_proxies
                        response = self.session.get(
                            url,
                            timeout=(10, 30),  # (连接超时, 读取超时)
                            verify=self.verify_ssl,
                            proxies=proxies_to_use,
                            headers={"Referer": url}  # 设置Referer为证书页面本身
                        )
                        response.raise_for_status()
                        print(f"[OK] 成功访问: {url}")
                        # 更新self.base_url为成功访问的URL（去掉/psa后缀）
                        self.base_url = base_url
                        return response.text
                    except requests.exceptions.ProxyError as e:
                        # 代理错误：尝试不使用代理直接连接
                        if not tried_without_proxy:
                            error_msg = str(e)
                            print(f"[代理错误] 代理连接失败，尝试不使用代理直接连接...")
                            print(f"  错误详情: {error_msg}")
                            tried_without_proxy = True
                            try:
                                self._throttle()
                                response = self.session.get(
                                    url,
                                    timeout=(10, 30),
                                    verify=self.verify_ssl,
                                    proxies=None,  # 不使用代理
                                    headers={"Referer": url}
                                )
                                response.raise_for_status()
                                print(f"[OK] 成功访问（不使用代理）: {url}")
                                self.base_url = base_url
                                return response.text
                            except Exception as e2:
                                last_error = e2
                                if attempt < self.max_retries - 1:
                                    delay = self.retry_delay * (2 ** attempt) + random.uniform(0.5, 1.0)
                                    print(f"  {delay:.2f}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                                    time.sleep(delay)
                                else:
                                    break
                        else:
                            # 已经尝试过不使用代理，仍然失败
                            last_error = e
                            if attempt < self.max_retries - 1:
                                delay = self.retry_delay * (2 ** attempt) + random.uniform(0.5, 1.0)
                                print(f"  {delay:.2f}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                                time.sleep(delay)
                            else:
                                break
                    except requests.exceptions.SSLError as e:
                        # SSL错误：如果不验证SSL，就禁用验证重试
                        if self.verify_ssl:
                            print(f"SSL错误，尝试禁用SSL验证...")
                            self.session.verify = False
                            try:
                                self._throttle()
                                self._maybe_rotate_identity()
                                # 如果已经尝试过不使用代理，SSL重试时也不使用代理
                                proxies_for_ssl = None if tried_without_proxy else self._current_proxies
                                response = self.session.get(
                                    url,
                                    timeout=(10, 30),  # (连接超时, 读取超时)
                                    verify=False,
                                    proxies=proxies_for_ssl,
                                    headers={"Referer": url}
                                )
                                response.raise_for_status()
                                print(f"[OK] 成功访问（禁用SSL验证）: {url}")
                                self.base_url = base_url
                                return response.text
                            except Exception as e2:
                                last_error = e2
                                break
                        else:
                            last_error = e
                            break
                    except requests.exceptions.ConnectionError as e:
                        # 连接错误：可能是网络问题、防火墙或网站不可用
                        error_msg = str(e)
                        # 如果是连接被拒绝且配置了代理但还没尝试不使用代理，尝试不使用代理
                        if (not tried_without_proxy and self._current_proxies and 
                            ("10061" in error_msg or "actively refused" in error_msg.lower() or "拒绝" in error_msg)):
                            print(f"[连接错误] 连接被拒绝，尝试不使用代理直接连接...")
                            print(f"  错误详情: {error_msg}")
                            tried_without_proxy = True
                            try:
                                self._throttle()
                                response = self.session.get(
                                    url,
                                    timeout=(10, 30),
                                    verify=self.verify_ssl,
                                    proxies=None,  # 不使用代理
                                    headers={"Referer": url}
                                )
                                response.raise_for_status()
                                print(f"[OK] 成功访问（不使用代理）: {url}")
                                self.base_url = base_url
                                return response.text
                            except Exception as e2:
                                last_error = e2
                                if attempt < self.max_retries - 1:
                                    delay = self.retry_delay * (2 ** attempt) + random.uniform(0.5, 1.0)
                                    print(f"  {delay:.2f}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                                    time.sleep(delay)
                                else:
                                    break
                        else:
                            if "10061" in error_msg or "actively refused" in error_msg.lower() or "拒绝" in error_msg:
                                print(f"[连接错误] 无法连接到服务器（可能被防火墙阻止或网站暂时不可用）")
                                print(f"  错误详情: {error_msg}")
                            else:
                                print(f"[连接错误] {error_msg}")
                            last_error = e
                            if attempt < self.max_retries - 1:
                                delay = self.retry_delay * (2 ** attempt) + random.uniform(0.5, 1.0)
                                print(f"  {delay:.2f}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                                time.sleep(delay)
                            else:
                                break
                    except requests.RequestException as e:
                        # 命中限制时延长退避并轮换身份
                        status = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                        if status in (429, 403):
                            wait_s = (1.5 * (2 ** attempt)) + random.uniform(0.3, 0.9)
                            print(f"命中限制（HTTP {status}），{wait_s:.2f}s 后重试并轮换身份...")
                            time.sleep(wait_s)
                            self._maybe_rotate_identity(force=True)
                        last_error = e
                        if attempt < self.max_retries - 1:
                            delay = self.retry_delay * (2 ** attempt) + random.uniform(0.1, 0.4)
                            print(f"请求失败，{delay:.2f}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                            time.sleep(delay)
                        else:
                            break
            
            # 如果这个URL失败了，尝试下一个
            if base_url != urls_to_try[-1]:  # 不是最后一个
                print(f"[X] 无法访问 {url}，尝试下一个URL...")
                time.sleep(0.8 + random.uniform(0.2, 0.8))  # 短暂随机延迟
        
        # 所有URL都失败了
        error_type = type(last_error).__name__ if last_error else "Unknown"
        error_msg = str(last_error) if last_error else "未知错误"
        
        # 提供更友好的错误消息
        if "10061" in error_msg or "actively refused" in error_msg.lower() or "拒绝" in error_msg:
            friendly_msg = (
                f"无法连接到PSA网站服务器\n"
                f"可能的原因：\n"
                f"  1. 网络连接问题\n"
                f"  2. 防火墙或代理设置阻止了连接\n"
                f"  3. PSA网站暂时不可用\n"
                f"\n尝试的URL:\n" + 
                "\n".join([f"  - {url}/{cert_number}" for url in urls_to_try]) + 
                f"\n\n错误详情: {error_type} - {error_msg}"
            )
        else:
            friendly_msg = (
                f"无法访问任何PSA网站页面\n"
                f"尝试的URL:\n" + 
                "\n".join([f"  - {url}/{cert_number}" for url in urls_to_try]) + 
                f"\n\n错误类型: {error_type}\n"
                f"错误详情: {error_msg}"
            )
        
        raise Exception(friendly_msg)
    
    def _find_image_urls(self, html: str) -> List[str]:
        """
        从HTML中提取高清图片URL
        
        Args:
            html: 页面HTML内容
            
        Returns:
            高清图片URL列表
        """
        soup = BeautifulSoup(html, 'html.parser')
        image_urls = []
        
        # 策略1: 查找所有img标签，优先寻找高清图片
        img_tags = soup.find_all('img')
        print(f"[DEBUG] 找到 {len(img_tags)} 个img标签")
        
        # 记录所有img标签的src属性（用于调试）
        if len(img_tags) > 0:
            print(f"[DEBUG] 前5个img标签的src属性:")
            for i, img in enumerate(img_tags[:5], 1):
                src = img.get('src') or img.get('data-src', '') or img.get('data-lazy-src', '') or '无src'
                print(f"  {i}. {str(src)[:150]}")
        
        # 首先查找明确标记为高清图的属性
        for img in img_tags:
            # 优先检查高清图属性
            for attr in ['data-highres', 'data-large', 'data-original', 'data-full', 'data-hires', 'data-src-large']:
                url = img.get(attr)
                if url:
                    full_url = urljoin(self.base_url, url)
                    if full_url not in image_urls and self._is_high_res_image(full_url):
                        image_urls.append(full_url)
                        print(f"[INFO] 从{attr}属性找到图片: {full_url}")
        
        # 然后查找普通src属性，但优先排除缩略图
        # 注意：策略4已经处理了/small/和/large/，这里处理其他格式的图片
        for img in img_tags:
            src = img.get('src') or img.get('data-src', '')
            if src:
                # 跳过已经在策略4中处理的 /small/、/large/、/medium/ URL
                if '/small/' in src or '/large/' in src or '/medium/' in src:
                    continue
                
                # 如果是PSA的CloudFront原图格式（没有路径部分），也要收集
                if '/cert/' in src and any(ext in src for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    # 检查是否是原图格式（已经在策略4中处理了）
                    if re.search(r'/cert/\d+/[^/]+\.(?:jpg|jpeg|png|webp)', src, re.I):
                        continue  # 已经在策略4中处理
                    
                src_lower = src.lower()
                # 跳过明显的缩略图（但不是PSA格式的）
                if any(keyword in src_lower for keyword in ['thumb', '_s.', '_m.']):
                    continue
                
                full_url = urljoin(self.base_url, src)
                if full_url not in image_urls and self._is_high_res_image(full_url):
                    image_urls.append(full_url)
        
        # 策略2: 查找包含图片的div或其他容器，可能包含背景图片
        divs_with_images = soup.find_all(['div', 'section'], class_=re.compile(r'image|photo|card', re.I))
        for div in divs_with_images:
            style = div.get('style', '')
            # 从style属性中提取url(...)
            bg_images = re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', style)
            for bg_url in bg_images:
                full_url = urljoin(self.base_url, bg_url)
                if self._is_high_res_image(full_url):
                    if full_url not in image_urls:
                        image_urls.append(full_url)
        
        # 策略3: 查找JavaScript中的数据，可能包含图片URL
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # 查找包含图片URL的模式
                urls = re.findall(r'["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', script.string, re.I)
                for url in urls:
                    if self._is_high_res_image(url):
                        if url not in image_urls:
                            image_urls.append(url)
        
        # 策略4: 优先查找PSA CloudFront URL（/small/、/large/、/medium/模式）- 这是PSA的标准图片URL格式
        # 查找所有包含 /small/、/large/、/medium/ 的URL，确保找到所有相关图片
        # 使用正则表达式直接匹配完整的CloudFront URL
        cloudfront_pattern = re.compile(r'https?://[^/]*cloudfront\.net/cert/\d+/(?:small|large|medium)/[^"\'>\s]+\.(?:jpg|jpeg|png|webp)', re.I)
        
        for img in img_tags:
            src = img.get('src') or img.get('data-src', '') or img.get('data-lazy-src', '') or img.get('data-original', '')
            if src:
                # 清理URL（移除反斜杠等）
                src = src.rstrip('\\/').strip()
                
                # 如果是完整的CloudFront URL，直接添加
                if 'cloudfront.net' in src.lower() and '/cert/' in src:
                    full_url = src if src.startswith('http') else urljoin(self.base_url, src)
                    full_url = full_url.rstrip('\\/').strip()
                    if full_url not in image_urls:
                        image_urls.append(full_url)
                        size_type = '小缩略图' if '/small/' in src else ('大缩略图' if '/large/' in src else ('中缩略图' if '/medium/' in src else '未知尺寸'))
                        print(f"[INFO] 找到PSA CloudFront图片URL（{size_type}）: {full_url}")
                # 查找所有PSA CloudFront URL格式（/small/、/large/、/medium/）
                elif '/small/' in src or '/large/' in src or '/medium/' in src:
                    full_url = urljoin(self.base_url, src) if not src.startswith('http') else src
                    full_url = full_url.rstrip('\\/').strip()  # 确保清理
                    if full_url not in image_urls:
                        image_urls.append(full_url)
                        size_type = '小缩略图' if '/small/' in src else ('大缩略图' if '/large/' in src else '中缩略图')
                        print(f"[INFO] 找到PSA图片URL（{size_type}）: {full_url}")
                
                # 也查找原图URL（没有路径部分的）
                elif '/cert/' in src and any(ext in src for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    # 检查是否是原图格式：/cert/{编号}/{文件名}.jpg
                    pattern = r'/cert/\d+/[^/]+\.(?:jpg|jpeg|png|webp)'
                    if re.search(pattern, src, re.I):
                        full_url = urljoin(self.base_url, src) if not src.startswith('http') else src
                        full_url = full_url.rstrip('\\/').strip()
                        if full_url not in image_urls:
                            image_urls.append(full_url)
                            print(f"[INFO] 找到PSA图片URL（原图）: {full_url}")
        
        # 也在HTML文本中直接搜索CloudFront URL（可能在某些属性或JavaScript中）
        cloudfront_urls = cloudfront_pattern.findall(html)
        print(f"[DEBUG] 在HTML文本中搜索CloudFront URL，找到 {len(cloudfront_urls)} 个匹配")
        for url in cloudfront_urls:
            url_clean = url.rstrip('\\/').strip()
            if url_clean not in image_urls:
                image_urls.append(url_clean)
                size_type = '小缩略图' if '/small/' in url_clean else ('大缩略图' if '/large/' in url_clean else ('中缩略图' if '/medium/' in url_clean else '未知尺寸'))
                print(f"[INFO] 从HTML文本中找到PSA CloudFront图片URL（{size_type}）: {url_clean}")
        
        # 策略5: 从已找到的图片URL中提取证书编号，尝试找到同一证书的其他图片（如正面、背面）
        if image_urls:
            # 从所有找到的URL中提取证书编号
            cert_nums = set()
            for url in image_urls:
                cert_match = re.search(r'/cert/(\d+)', url)
                if cert_match:
                    cert_nums.add(cert_match.group(1))
            
            # 对每个证书编号，尝试找到所有可能的图片
            for cert_num in cert_nums:
                # 从已找到的URL中提取文件名模式
                found_filenames = []
                for url in image_urls:
                    if f'/cert/{cert_num}/' in url:
                        filename_match = re.search(r'/cert/\d+/(?:small|large|medium)/([^/?\\]+)', url)
                        if filename_match:
                            found_filenames.append(filename_match.group(1))
                        # 也提取原图文件名
                        orig_match = re.search(r'/cert/\d+/([^/?\\]+\.(?:jpg|jpeg|png|webp))', url)
                        if orig_match and '/small/' not in url and '/large/' not in url and '/medium/' not in url:
                            found_filenames.append(orig_match.group(1))
                
                # 如果找到文件名，尝试找到同一证书的其他图片（不同文件名或不同尺寸）
                base_match = re.search(r'(https?://[^/]+/cert/\d+)', image_urls[0])
                if base_match:
                    base_path = base_match.group(1)
                    
                    # 尝试所有尺寸的所有文件名组合
                    for filename in found_filenames:
                        for size in ['small', 'large', 'medium']:
                            test_url = f"{base_path}/{size}/{filename}"
                            if test_url not in image_urls:
                                try:
                                    self._throttle()
                                    response = self.session.head(test_url, timeout=3, allow_redirects=True, verify=self.verify_ssl, proxies=self._current_proxies)
                                    if response.status_code == 200:
                                        content_type = response.headers.get('Content-Type', '')
                                        if 'image' in content_type:
                                            image_urls.append(test_url)
                                            print(f"[INFO] 找到同一证书的其他图片: {test_url}")
                                except:
                                    continue
                    
                    # 也尝试原图格式
                    for filename in found_filenames:
                        test_url = f"{base_path}/{filename}"
                        if test_url not in image_urls:
                            try:
                                self._throttle()
                                response = self.session.head(test_url, timeout=3, allow_redirects=True, verify=self.verify_ssl, proxies=self._current_proxies)
                                if response.status_code == 200:
                                    content_type = response.headers.get('Content-Type', '')
                                    if 'image' in content_type:
                                        image_urls.append(test_url)
                                        print(f"[INFO] 找到同一证书的原图: {test_url}")
                            except:
                                continue
                
                # 也尝试API端点
                base_domain = urlparse(self.base_url).netloc
                high_res_api_urls = [
                    f"https://{base_domain}/api/cert/{cert_num}/front",
                    f"https://{base_domain}/api/cert/{cert_num}/back",
                    f"https://{base_domain}/cert/{cert_num}/front",
                    f"https://{base_domain}/cert/{cert_num}/back",
                ]
                for api_url in high_res_api_urls:
                    if api_url not in image_urls:
                        try:
                            self._throttle()
                            response = self.session.head(api_url, timeout=3, allow_redirects=True, verify=self.verify_ssl, proxies=self._current_proxies)
                            if response.status_code == 200:
                                content_type = response.headers.get('Content-Type', '')
                                if 'image' in content_type:
                                    image_urls.append(api_url)
                                    print(f"[INFO] 找到API图片: {api_url}")
                        except:
                            continue
        
        # 策略6: 从页面中查找data属性中的高清图URL
        for img in img_tags:
            # 检查更多可能的data属性
            for attr in ['data-highres', 'data-large', 'data-original', 'data-full', 'data-hires']:
                url = img.get(attr)
                if url:
                    full_url = urljoin(self.base_url, url)
                    if full_url not in image_urls and self._is_high_res_image(full_url):
                        image_urls.append(full_url)
        
        # 去重并排序：优先返回包含highres、large、original等关键词的URL
        def sort_key(url):
            url_lower = url.lower()
            if 'highres' in url_lower or 'high-res' in url_lower:
                return 0
            elif 'large' in url_lower or 'original' in url_lower:
                return 1
            elif 'thumb' in url_lower or 'small' in url_lower:
                return 3  # 缩略图优先级最低
            else:
                return 2
        
        # 去重并排序，返回所有找到的图片（不限制数量）
        image_urls_sorted = sorted(set(image_urls), key=sort_key)
        print(f"[DEBUG] _find_image_urls 总共找到 {len(image_urls_sorted)} 张图片（去重后）")
        if len(image_urls_sorted) == 0:
            print(f"[DEBUG] 警告：未找到任何图片URL，HTML长度: {len(html)} 字符")
        return image_urls_sorted  # 返回所有找到的图片
    
    def _filter_images_by_cert(self, image_urls: List[str], cert_number: str) -> List[str]:
        """
        过滤图片URL列表，只保留包含指定证书编号的URL
        
        Args:
            image_urls: 图片URL列表
            cert_number: 证书编号（纯数字）
            
        Returns:
            过滤后的图片URL列表（只包含指定证书编号的图片）
        """
        if not image_urls:
            return []
        
        cert_num = self._extract_cert_number(cert_number)
        filtered_urls = []
        
        for url in image_urls:
            if not url:
                continue
                
            url_clean = url.strip()
            # 检查URL中是否包含当前证书编号
            # PSA URL格式: /cert/{编号}/... 或 /cert/{编号}/small/... 等
            # 支持格式：
            # - https://cloudfront.net/cert/{编号}/small/{文件名}.jpg
            # - https://cloudfront.net/cert/{编号}/large/{文件名}.jpg
            # - https://cloudfront.net/cert/{编号}/{文件名}.jpg
            cert_match = re.search(r'/cert/(\d+)', url_clean)
            if cert_match:
                url_cert_num = cert_match.group(1)
                if url_cert_num == cert_num:
                    filtered_urls.append(url)
                    print(f"[OK] 保留匹配的图片URL（证书编号 {url_cert_num}）: {url_clean[:100]}")
                else:
                    print(f"[INFO] 过滤掉不匹配的图片URL（证书编号 {url_cert_num}，期望 {cert_num}）: {url_clean[:100]}")
            else:
                # 如果URL不包含 /cert/ 格式，检查是否包含证书编号作为路径的一部分
                # 例如: https://domain.com/{证书编号}/image.jpg
                if (f'/{cert_num}/' in url_clean or 
                    url_clean.endswith(f'/{cert_num}') or 
                    f'/{cert_num}_' in url_clean or 
                    f'_{cert_num}.' in url_clean or
                    f'/cert/{cert_num}' in url_clean):
                    filtered_urls.append(url)
                else:
                    # 如果URL不包含明确的证书编号，过滤掉
                    print(f"[INFO] 过滤掉不包含证书编号的图片URL: {url_clean[:100]}")
        
        if len(filtered_urls) < len(image_urls):
            print(f"[INFO] 过滤前: {len(image_urls)} 张图片，过滤后: {len(filtered_urls)} 张图片（证书编号: {cert_num}）")
        elif len(filtered_urls) == 0 and len(image_urls) > 0:
            print(f"[WARNING] 所有图片都被过滤掉了！")
            print(f"[WARNING] 原始图片列表（前3个）:")
            for i, u in enumerate(image_urls[:3], 1):
                print(f"  {i}. {u[:100]}")
        
        return filtered_urls
    
    def _filter_unnecessary_files(self, image_urls: List[str]) -> List[str]:
        """
        过滤掉不必要的文件（如table-image-certified.png等非卡片图片）
        
        Args:
            image_urls: 图片URL列表
            
        Returns:
            过滤后的URL列表（排除不必要的文件）
        """
        if not image_urls:
            return []
        
        # 定义需要过滤的文件名关键词
        exclude_keywords = [
            'table-image',
            'certified',
            'logo',
            'icon',
            'button',
            'badge',
            'avatar',
            'spinner',
            'loading',
            'placeholder',
            'og-meta',  # Open Graph meta图片
            'meta',     # 其他meta图片
            'og-image', # Open Graph图片
            'social',   # 社交媒体图片
            'share',    # 分享图片
        ]
        
        filtered_urls = []
        for url in image_urls:
            url_lower = url.lower()
            filename = os.path.basename(urlparse(url).path).lower()
            
            # 检查文件名是否包含排除关键词
            should_exclude = any(keyword in filename for keyword in exclude_keywords)
            
            if should_exclude:
                print(f"[INFO] 过滤掉不必要的文件: {filename}")
            else:
                filtered_urls.append(url)
        
        if len(filtered_urls) < len(image_urls):
            print(f"[INFO] 排除不必要文件：{len(image_urls)} -> {len(filtered_urls)}")
        
        return filtered_urls
    
    def _deduplicate_by_filename(self, image_urls: List[str]) -> List[str]:
        """
        基于文件名去重（同一个文件名只保留一个URL）
        
        Args:
            image_urls: 图片URL列表
            
        Returns:
            去重后的URL列表
        """
        if not image_urls:
            return []
        
        seen_filenames = {}
        deduplicated_urls = []
        
        for url in image_urls:
            # 提取文件名（从URL路径中）
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path).rstrip('\\/')
            
            # 如果没有文件名或文件名无效，保留URL
            if not filename or '.' not in filename:
                deduplicated_urls.append(url)
                continue
            
            # 如果这个文件名还没见过，保留这个URL
            if filename not in seen_filenames:
                seen_filenames[filename] = url
                deduplicated_urls.append(url)
            else:
                # 如果已经见过这个文件名，检查URL是否相同
                if url != seen_filenames[filename]:
                    print(f"[INFO] 发现重复文件名 {filename}，保留第一个URL: {seen_filenames[filename][:100]}")
                    print(f"[INFO] 跳过重复URL: {url[:100]}")
                else:
                    print(f"[INFO] 跳过完全相同的URL: {url[:100]}")
        
        if len(deduplicated_urls) < len(image_urls):
            print(f"[INFO] 去重：{len(image_urls)} -> {len(deduplicated_urls)} 个唯一文件")
        
        return deduplicated_urls
    
    def _is_high_res_image(self, url: str) -> bool:
        """
        判断URL是否可能是高清图片
        
        Args:
            url: 图片URL
            
        Returns:
            是否是高清图片
        """
        url_lower = url.lower()
        
        # 排除明显不是卡片图片的URL
        exclude_keywords = ['logo', 'icon', 'avatar', 'button', 'badge', 'flag', 'spinner']
        if any(keyword in url_lower for keyword in exclude_keywords):
            return False
        
        # 检查是否是图片文件
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if not any(ext in url_lower for ext in image_extensions):
            return False
        
        # 优先选择包含高清标识的URL
        high_res_keywords = ['highres', 'high-res', 'high_res', 'large', 'original', 'full', 
                           'hd', 'high', 'big', 'max', 'cert']
        if any(keyword in url_lower for keyword in high_res_keywords):
            return True
        
        # 如果URL包含明显的图片路径（如/cert/相关的路径），也认为是可能的图片
        if '/cert/' in url_lower or 'card' in url_lower or 'image' in url_lower:
            # 检查文件大小标识（如文件名中包含尺寸信息）
            if re.search(r'\d{3,4}x\d{3,4}', url_lower):
                return True
            return True
        
        return False
    
    def _convert_to_large_thumbnail(self, small_url: str) -> Optional[str]:
        """
        将小缩略图URL转换为大缩略图URL（用于预览）
        PSA URL模式: /cert/{编号}/small/{文件名} -> /cert/{编号}/large/{文件名}
        
        Args:
            small_url: 小缩略图URL（包含/small/或/medium/）
            
        Returns:
            大缩略图URL（包含/large/），如果无法转换则返回None
        """
        # 清理URL
        small_url = small_url.rstrip('\\/').strip()
        
        if '/small/' in small_url:
            large_url = small_url.replace('/small/', '/large/')
            return large_url.rstrip('\\/')
        elif '/medium/' in small_url:
            # medium也可以转换为large
            large_url = small_url.replace('/medium/', '/large/')
            return large_url.rstrip('\\/')
        return None
    
    def _convert_to_size(self, url: str, target_size: str) -> Optional[str]:
        """
        将图片URL转换为指定尺寸的URL
        
        PSA URL模式:
        - 原图: /cert/{编号}/{文件名}
        - 大缩略图: /cert/{编号}/large/{文件名}
        - 中缩略图: /cert/{编号}/medium/{文件名}
        - 小缩略图: /cert/{编号}/small/{文件名}
        
        Args:
            url: 图片URL（可能包含/small/、/large/、/medium/或已经是原图）
            target_size: 目标尺寸 ('original', 'large', 'medium', 'small')
            
        Returns:
            转换后的URL，如果无法转换则返回None
        """
        # 清理URL（移除末尾的反斜杠和其他字符）
        url = url.rstrip('\\/').strip()
        
        # 检查是否是PSA的CloudFront URL模式
        # 修复：明确匹配包含尺寸路径的URL：/cert/{编号}/{尺寸}/{文件名}
        # 或者已经是原图的URL：/cert/{编号}/{文件名}
        pattern_with_size = r'(https?://[^/]+/cert/\d+)/(small|large|medium|thumb)/([^/?\\]+\.(?:jpg|jpeg|png|webp))'
        pattern_original = r'(https?://[^/]+/cert/\d+)/([^/?\\]+\.(?:jpg|jpeg|png|webp))'
        
        # 先尝试匹配包含尺寸路径的URL
        match = re.search(pattern_with_size, url, re.I)
        if match:
            base_path = match.group(1)
            size_path = match.group(2).lower()
            filename = match.group(3).strip('\\/')  # 清理文件名中的反斜杠
            
            # 根据目标尺寸构造URL
            if target_size == 'original':
                return f"{base_path}/{filename}"
            elif target_size == 'large':
                return f"{base_path}/large/{filename}"
            elif target_size == 'medium':
                return f"{base_path}/medium/{filename}"
            elif target_size == 'small':
                return f"{base_path}/small/{filename}"
        
        # 如果上面没匹配到，尝试匹配已经是原图的URL
        match = re.search(pattern_original, url, re.I)
        if match:
            base_path = match.group(1)
            filename = match.group(2).strip('\\/')
            
            # 如果已经是原图，根据目标尺寸构造URL
            if target_size == 'original':
                return f"{base_path}/{filename}"
            elif target_size == 'large':
                return f"{base_path}/large/{filename}"
            elif target_size == 'medium':
                return f"{base_path}/medium/{filename}"
            elif target_size == 'small':
                return f"{base_path}/small/{filename}"
        
        return None
    
    def get_high_res_images(self, cert_number: str, preview_mode: bool = False, image_size: str = 'original') -> Tuple[List[str], str]:
        """
        获取指定证书编号的图片URL列表
        
        Args:
            cert_number: PSA证书编号（可以是纯数字或包含前缀的字符串）
            preview_mode: 如果为True，返回大缩略图URL（/large/，用于预览）；
                         如果为False，根据image_size参数返回对应尺寸的URL（用于下载）
            image_size: 图片尺寸 ('original', 'large', 'medium', 'small')
                       - 'original': 原图（移除/small/、/large/、/medium/）
                       - 'large': 大缩略图（/large/）
                       - 'medium': 中缩略图（/medium/）
                       - 'small': 小缩略图（/small/）
            
        Returns:
            (图片URL列表, 页面标题)
        """
        # 提取纯数字证书编号
        cert_num = self._extract_cert_number(cert_number)
        
        # 获取页面HTML
        html = self._get_page_html(cert_num)
        print(f"[DEBUG] 获取到HTML，长度: {len(html)} 字符")
        
        # 提取页面标题
        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.find('title')
        page_title = title_tag.text.strip() if title_tag else f"PSA Certificate {cert_num}"
        print(f"[DEBUG] 页面标题: {page_title}")
        
        # 查找图片URL（找到的可能是/small/或/large/）
        image_urls = self._find_image_urls(html)
        print(f"[INFO] 从HTML中找到 {len(image_urls)} 张图片")
        
        if not image_urls:
            print("[WARNING] 未能从HTML中找到图片，尝试使用备用方法...")
            # 备用方法: 直接尝试常见的PSA图片URL模式
            image_urls = self._try_common_url_patterns(cert_num)
            print(f"[INFO] 备用方法找到 {len(image_urls)} 张图片")
            if len(image_urls) == 0:
                print(f"[WARNING] 备用方法也未找到图片，证书编号: {cert_num}")
        
        # 先不过滤证书编号，保留所有找到的图片URL
        # 因为转换过程需要基于找到的URL进行，如果提前过滤可能会丢失有效的small/medium URL
        # 转换后再进行过滤和验证
        filtered_image_urls = image_urls if image_urls else []
        
        if not filtered_image_urls:
            print(f"[WARNING] 未找到任何图片，尝试使用备用方法...")
            # 备用方法: 直接尝试常见的PSA图片URL模式
            backup_urls = self._try_common_url_patterns(cert_num)
            if backup_urls:
                filtered_image_urls = backup_urls
                print(f"[INFO] 备用方法找到 {len(backup_urls)} 张图片")
        
        # 根据模式转换URL（在转换前先不过滤，转换后再过滤）
        # 这样即使找到了small/medium的URL，也能正确转换和保留
        converted_urls = []
        print(f"[INFO] 开始转换URL，模式：{'预览(large)' if preview_mode else '下载(original)'}")
        
        for url in filtered_image_urls:
            url_clean = url.rstrip('\\/').strip()  # 先清理URL
            
            if preview_mode:
                # 预览模式：强制转换为大缩略图（/large/）
                if '/small/' in url_clean:
                    # 方法1：使用转换函数
                    large_url = self._convert_to_large_thumbnail(url_clean)
                    if large_url:
                        converted_urls.append(large_url.rstrip('\\/'))
                        print(f"[INFO] 预览模式：small -> large {url_clean[:80]} -> {large_url[:80]}")
                    else:
                        # 方法2：直接替换路径
                        large_url = url_clean.replace('/small/', '/large/')
                        converted_urls.append(large_url.rstrip('\\/'))
                        print(f"[INFO] 预览模式：small -> large（直接替换） {url_clean[:80]} -> {large_url[:80]}")
                elif '/medium/' in url_clean:
                    # medium转换为large
                    large_url = url_clean.replace('/medium/', '/large/')
                    converted_urls.append(large_url.rstrip('\\/'))
                    print(f"[INFO] 预览模式：medium -> large {url_clean[:80]} -> {large_url[:80]}")
                elif '/large/' in url_clean:
                    # 已经是大缩略图，直接使用
                    converted_urls.append(url_clean.rstrip('\\/'))
                    print(f"[INFO] 预览模式：已是large {url_clean[:80]}")
                else:
                    # 如果是原图格式（没有size路径），尝试转换为large
                    # 原图: /cert/{编号}/{文件名}.jpg -> /cert/{编号}/large/{文件名}.jpg
                    # 使用_convert_to_size方法，更可靠
                    large_url = self._convert_to_size(url_clean, 'large')
                    if large_url:
                        converted_urls.append(large_url.rstrip('\\/'))
                        print(f"[INFO] 预览模式：原图 -> large {url_clean[:80]} -> {large_url[:80]}")
                    else:
                        # 如果_convert_to_size失败，尝试正则匹配
                        orig_match = re.search(r'(https?://[^/]+/cert/\d+)/([^/?\\]+\.(?:jpg|jpeg|png|webp))', url_clean, re.I)
                        if orig_match:
                            base_path = orig_match.group(1)
                            filename = orig_match.group(2).strip('\\/')
                            large_url = f"{base_path}/large/{filename}"
                            converted_urls.append(large_url.rstrip('\\/'))
                            print(f"[INFO] 预览模式：原图 -> large（正则匹配） {url_clean[:80]} -> {large_url[:80]}")
                        else:
                            # 无法识别格式，但如果是PSA URL，尝试直接添加/large/
                            if '/cert/' in url_clean and any(ext in url_clean for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                # 尝试在/cert/{编号}/之后插入large/
                                large_url = re.sub(r'(/cert/\d+)/([^/?\\]+\.(?:jpg|jpeg|png|webp))', r'\1/large/\2', url_clean, flags=re.I)
                                if large_url != url_clean:
                                    converted_urls.append(large_url.rstrip('\\/'))
                                    print(f"[INFO] 预览模式：原图 -> large（插入路径） {url_clean[:80]} -> {large_url[:80]}")
                                else:
                                    # 最后尝试：保留原URL（可能是其他格式的URL）
                                    converted_urls.append(url_clean.rstrip('\\/'))
                                    print(f"[WARNING] 预览模式：无法识别URL格式，保留原URL {url_clean[:80]}")
                            else:
                                # 不是PSA URL格式，保留原URL
                                converted_urls.append(url_clean.rstrip('\\/'))
                                print(f"[WARNING] 预览模式：非PSA URL格式，保留原URL {url_clean[:80]}")
            else:
                # 下载模式：强制使用原图（不管image_size参数是什么）
                # 将任何尺寸的URL转换为原图
                if '/small/' in url_clean or '/large/' in url_clean or '/medium/' in url_clean:
                    # 转换为原图：移除 /small/、/large/、/medium/
                    orig_url = self._convert_to_size(url_clean, 'original')
                    if orig_url:
                        converted_urls.append(orig_url)
                        print(f"[INFO] 下载模式：转换为原图 {url_clean[:80]} -> {orig_url[:80]}")
                    else:
                        # 手动构造原图URL（移除size路径）
                        # 例如：/cert/123/large/file.jpg -> /cert/123/file.jpg
                        orig_url = re.sub(r'/(?:small|large|medium)/', '/', url_clean)
                        converted_urls.append(orig_url)
                        print(f"[INFO] 下载模式：手动转换为原图 {url_clean[:80]} -> {orig_url[:80]}")
                else:
                    # 已经是原图格式
                    converted_urls.append(url_clean)
                    print(f"[INFO] 下载模式：已是原图格式 {url_clean[:80]}")
        
        print(f"[INFO] URL转换完成：{len(filtered_image_urls)} -> {len(converted_urls)}")
        
        # 在过滤前，检查转换后的URL是否包含证书编号
        urls_without_cert = []
        for url in converted_urls:
            cert_match = re.search(r'/cert/(\d+)', url)
            if not cert_match:
                urls_without_cert.append(url)
        
        if urls_without_cert:
            print(f"[WARNING] 转换后有 {len(urls_without_cert)} 个URL不包含证书编号格式:")
            for url in urls_without_cert[:3]:
                print(f"  - {url[:100]}")
        
        # 转换后过滤证书编号：确保转换后的URL属于当前证书编号
        # 对于PSA Japan等特殊情况，页面中显示的图片证书编号可能与页面URL的证书编号不一致
        # 在预览模式下，应该放宽条件，保留页面中找到的所有图片
        
        # 检查转换后的URL中有哪些不同的证书编号
        found_cert_nums = set()
        urls_with_cert = []
        for url in converted_urls:
            cert_match = re.search(r'/cert/(\d+)', url)
            if cert_match:
                found_cert_nums.add(cert_match.group(1))
                urls_with_cert.append(url)
        
        # 在预览模式下，如果页面中找到的图片证书编号与页面URL不一致，
        # 说明可能是PSA Japan等特殊情况，应该保留这些图片
        if preview_mode and found_cert_nums and cert_num not in found_cert_nums:
            print(f"[INFO] 预览模式：页面中找到的图片证书编号 {', '.join(found_cert_nums)} 与页面URL证书编号 {cert_num} 不一致")
            print(f"[INFO] 预览模式：这是PSA Japan等特殊情况，保留页面中找到的所有图片用于预览")
            # 在预览模式下，保留所有找到的图片（最多保留前4个，通常是front和back）
            final_urls = urls_with_cert[:4]  # 最多保留4个（通常是2张front + 2张back）
            print(f"[INFO] 预览模式：保留了 {len(final_urls)} 个URL用于预览")
        else:
            # 正常过滤：只保留属于当前证书编号的图片
            final_urls_before_filter = converted_urls.copy()
            final_urls = self._filter_images_by_cert(converted_urls, cert_num)
            
            # 如果过滤后没有图片，但转换前有图片，说明所有图片的证书编号都不匹配
            # 在预览模式下，如果所有URL都被过滤掉，尝试放宽过滤条件
            if len(final_urls) == 0 and len(converted_urls) > 0:
                print(f"[WARNING] 转换后所有图片的证书编号都不匹配（期望 {cert_num}）")
                print(f"[INFO] 页面中显示的图片证书编号与页面URL不一致")
                
                if found_cert_nums:
                    print(f"[INFO] 页面中找到的图片证书编号: {', '.join(found_cert_nums)}（期望 {cert_num}）")
                    
                    # 在预览模式下，如果所有URL都被过滤掉，尝试放宽条件
                    if preview_mode:
                        # 优先尝试保留不包含证书编号的URL（可能是其他格式）
                        if urls_without_cert:
                            print(f"[INFO] 预览模式：尝试保留不包含证书编号的URL（可能是其他格式）")
                            final_urls = urls_without_cert[:2]  # 最多保留2个
                            print(f"[INFO] 预览模式：保留了 {len(final_urls)} 个不包含证书编号的URL")
                        else:
                            # 如果没有不包含证书编号的URL，在预览模式下放宽条件，保留前几个URL
                            print(f"[INFO] 预览模式：放宽过滤条件，保留前 {min(2, len(urls_with_cert))} 个URL用于预览")
                            final_urls = urls_with_cert[:2]  # 最多保留2个
                            print(f"[INFO] 预览模式：保留了 {len(final_urls)} 个URL（证书编号可能不匹配）")
                    else:
                        print(f"[WARNING] 严格过滤：不保留证书编号不匹配的图片，返回空列表")
                        final_urls = []
                else:
                    # 如果没有找到任何证书编号，在预览模式下尝试保留这些URL
                    if preview_mode:
                        if urls_without_cert:
                            print(f"[INFO] 预览模式：未找到明确的证书编号，但保留不包含证书编号的URL")
                            final_urls = urls_without_cert[:2]  # 最多保留2个
                        else:
                            # 如果连不包含证书编号的URL都没有，保留前几个转换后的URL
                            print(f"[INFO] 预览模式：未找到明确的证书编号，保留前 {min(2, len(converted_urls))} 个转换后的URL")
                            final_urls = converted_urls[:2]  # 最多保留2个
                    else:
                        print(f"[WARNING] 未找到明确的证书编号，返回空列表")
                        final_urls = []
            elif len(final_urls) < len(converted_urls):
                print(f"[INFO] 转换后过滤：{len(converted_urls)} -> {len(final_urls)}（部分图片证书编号不匹配）")
                # 显示被过滤的URL信息
                filtered_out = [url for url in converted_urls if url not in final_urls]
                for url in filtered_out[:3]:
                    cert_match = re.search(r'/cert/(\d+)', url)
                    if cert_match:
                        url_cert_num = cert_match.group(1)
                        print(f"  [过滤] URL证书编号 {url_cert_num} != 期望 {cert_num}: {url[:80]}")
        
        # 过滤掉不必要的文件（如table-image-certified.png等非卡片图片）
        final_urls = self._filter_unnecessary_files(final_urls)
        
        # 去重：基于文件名去重（同一个文件名只保留一个URL）
        final_urls = self._deduplicate_by_filename(final_urls)
        
        print(f"[INFO] 最终返回 {len(final_urls)} 张图片（已去重）")
        return final_urls, page_title
    
    def _try_common_url_patterns(self, cert_number: str) -> List[str]:
        """
        尝试使用常见的PSA图片URL模式
        
        Args:
            cert_number: 证书编号
            
        Returns:
            可能的图片URL列表
        """
        possible_urls = []
        
        # 从base_url提取域名
        base_domain = urlparse(self.base_url).netloc
        
        # PSA常见的图片URL模式（尝试多种尺寸和方向）
        # 首先尝试从CloudFront URL格式（最常见的格式）
        patterns = []
        
        # 尝试从已知的CloudFront域名构建URL（如果base_url是CloudFront）
        if 'cloudfront.net' in base_domain:
            # 尝试不同的尺寸和方向
            for size in ['small', 'large', 'medium']:
                # 尝试front和back
                for side in ['front', 'back', '']:
                    if side:
                        patterns.append(f"https://{base_domain}/cert/{cert_number}/{size}/{side}.jpg")
                    else:
                        # 也尝试不带方向的（可能需要从页面中获取实际文件名）
                        patterns.append(f"https://{base_domain}/cert/{cert_number}/{size}/")
        
        # 也尝试原图格式
        patterns.extend([
            f"{self.base_url}/{cert_number}/front",
            f"{self.base_url}/{cert_number}/back",
            f"https://{base_domain}/api/cert/{cert_number}/front",
            f"https://{base_domain}/api/cert/{cert_number}/back",
        ])
        
        # 也尝试其他域名
        for backup_url in self.backup_urls:
            backup_domain = urlparse(backup_url).netloc
            if 'cloudfront.net' in backup_domain:
                for size in ['small', 'large']:
                    patterns.extend([
                        f"https://{backup_domain}/cert/{cert_number}/{size}/front.jpg",
                        f"https://{backup_domain}/cert/{cert_number}/{size}/back.jpg",
                    ])
            else:
                patterns.extend([
                    f"{backup_url}/{cert_number}/front",
                    f"{backup_url}/{cert_number}/back",
                ])
        
        # 测试所有模式
        for url in patterns:
            if url in possible_urls:
                continue
            try:
                self._throttle()
                response = self.session.head(url, timeout=3, allow_redirects=True, verify=self.verify_ssl, proxies=self._current_proxies)
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' in content_type:
                        possible_urls.append(url)
                        print(f"[INFO] 通过备用模式找到图片: {url}")
            except:
                continue
        
        return possible_urls
    
    def download_image(self, url: str, save_path: Path, filename: str = None) -> bool:
        """
        下载单张图片
        
        Args:
            url: 图片URL
            save_path: 保存目录路径
            filename: 保存的文件名，如果为None则从URL中提取
            
        Returns:
            是否下载成功
        """
        try:
            print(f"正在下载: {url}")
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # 确定文件名
            if not filename:
                parsed_url = urlparse(url)
                filename = os.path.basename(parsed_url.path)
                if not filename or '.' not in filename:
                    filename = f"image_{int(time.time())}.jpg"
            
            # 确保保存目录存在
            save_path.mkdir(parents=True, exist_ok=True)
            
            # 保存文件
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
            
            print(f"\n[OK] 已保存: {file_path}")
            print(f"  文件大小: {downloaded / 1024:.2f} KB")
            return True
            
        except Exception as e:
            print(f"\n[X] 下载失败: {url}\n  错误: {str(e)}")
            return False

    # ---------------- 防封/限速辅助 ----------------
    def _throttle(self):
        base_interval = self.min_request_interval
        jitter = random.uniform(0.05, 0.2)
        now = time.time()
        wait = (self._last_request_ts + base_interval + jitter) - now
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.time()

    def _maybe_rotate_identity(self, force: bool = False):
        if force or random.random() < 0.35:
            self.session.headers["User-Agent"] = random.choice(self._user_agents)
        if self._proxy_pool:
            if force or random.random() < 0.25:
                proxy = random.choice(self._proxy_pool)
                if proxy.lower().startswith("http"):
                    self._current_proxies = {"http": proxy, "https": proxy}
                else:
                    self._current_proxies = None
        else:
            self._current_proxies = None
    
    def download_images(self, cert_number: str, save_dir: str = "downloads") -> bool:
        """
        下载指定证书编号的所有高清图片，并收集Item Information
        
        Args:
            cert_number: PSA证书编号
            save_dir: 保存目录
            
        Returns:
            是否成功下载至少一张图片
        """
        try:
            # 提取证书编号
            cert_num = self._extract_cert_number(cert_number)
            
            # 创建保存目录
            save_path = Path(save_dir) / f"PSA_{cert_num}"
            save_path.mkdir(parents=True, exist_ok=True)
            
            # 获取页面HTML以提取Item Information
            print("\n正在获取页面信息...")
            html = self._get_page_html(cert_num)
            
            # 提取Item Information
            print("正在提取Item Information...")
            item_info_extractor = PSAItemInfoExtractor()
            item_info = item_info_extractor.extract_item_info(html)
            
            if item_info:
                # 保存Item Information文件
                item_info_file = item_info_extractor.save_item_info_text(item_info, save_path, cert_num)
                print(f"[OK] Item Information已保存: {item_info_file}")
                
                # 显示提取到的关键信息
                brand_title = item_info_extractor.get_brand_title(item_info)
                if brand_title:
                    print(f"[INFO] Brand/Title: {brand_title}")
            else:
                print("[WARNING] 未能提取到Item Information")
            
            # 获取高清图片URL
            print("\n正在查找图片...")
            image_urls, page_title = self.get_high_res_images(cert_number)
            
            if not image_urls:
                print(f"错误: 未能找到证书编号 {cert_number} 的图片")
                # 即使没有图片，如果成功提取了Item Information，也算部分成功
                if item_info:
                    print(f"[INFO] 已保存Item Information到: {save_path.absolute()}")
                    return True
                return False
            
            print(f"\n找到 {len(image_urls)} 张图片:")
            for i, url in enumerate(image_urls, 1):
                print(f"  {i}. {url}")
            
            # 下载所有图片
            success_count = 0
            for i, url in enumerate(image_urls, 1):
                filename = f"image_{i}_{os.path.basename(urlparse(url).path)}"
                if '.' not in filename:
                    filename += '.jpg'
                
                if self.download_image(url, save_path, filename):
                    success_count += 1
                print()  # 空行分隔
            
            if success_count > 0:
                print(f"\n[OK] 成功下载 {success_count}/{len(image_urls)} 张图片")
                print(f"保存位置: {save_path.absolute()}")
                if item_info:
                    print(f"[OK] Item Information已保存: {save_path / f'{cert_num}_item_info.txt'}")
                return True
            else:
                print("\n[X] 所有图片下载失败")
                # 即使图片下载失败，如果成功提取了Item Information，也算部分成功
                if item_info:
                    print(f"[INFO] 已保存Item Information到: {save_path.absolute()}")
                    return True
                return False
                
        except Exception as e:
            print(f"\n[X] 下载过程出错: {str(e)}")
            return False


def main():
    """主程序入口"""
    print("=" * 60)
    print("PSA卡片高清图片下载器")
    print("=" * 60)
    print()
    
    # 创建下载器实例
    downloader = PSACardImageDownloader()
    
    # 交互式输入
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


if __name__ == "__main__":
    main()

