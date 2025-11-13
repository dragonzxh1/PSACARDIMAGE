"""
PSA证书页面Item Information提取器
从PSA证书页面提取Item Information信息，包括Brand/Title等字段
"""

import re
from bs4 import BeautifulSoup
from typing import Dict, Optional
from pathlib import Path
import json


class PSAItemInfoExtractor:
    """PSA Item Information提取器"""
    
    def __init__(self):
        """初始化提取器"""
        pass
    
    def extract_item_info(self, html: str) -> Dict[str, str]:
        """
        从HTML中提取Item Information
        
        Args:
            html: 页面HTML内容
            
        Returns:
            包含Item Information的字典，键为字段名，值为字段值
        """
        soup = BeautifulSoup(html, 'html.parser')
        item_info = {}
        
        # 方法0: 优先尝试从Next.js序列化的script标签中提取（适用于psacard.co.jp）
        item_info = self._extract_from_nextjs_scripts(soup)
        
        # 方法1: 查找包含"Item Information"的标题或区域
        if not item_info:
            item_info_section = self._find_item_info_section(soup)
            
            if item_info_section:
                # 从找到的区域提取信息
                item_info = self._extract_from_section(item_info_section)
        
        # 方法2: 如果方法1失败，尝试查找表格结构
        if not item_info:
            item_info = self._extract_from_tables(soup)
        
        # 方法3: 如果方法2也失败，尝试查找包含常见字段名的元素
        if not item_info:
            item_info = self._extract_from_elements(soup)
        
        # 移除日文的 title 相关字段，只保留英文的 title
        japanese_title_keys = ['ブランド／タイトル', 'タイトル']
        for key in japanese_title_keys:
            if key in item_info:
                del item_info[key]
        
        return item_info
    
    def _extract_from_nextjs_scripts(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        从Next.js序列化的script标签中提取Item Information
        适用于psacard.co.jp（日文）和psacard.com（英文）等使用Next.js的网站
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Item Information字典
        """
        item_info = {}
        
        # 日文和英文字段名映射（双向映射）
        field_mapping = {
            # 日文 -> 英文
            '証明番号': 'Certificate Number',
            '発行年': 'Year',
            'ブランド／タイトル': 'Brand/Title',
            'ブランド': 'Brand',
            'タイトル': 'Title',
            'カード番号': 'Card Number',
            'サブジェクト': 'Subject',
            'グレード': 'Grade',
            'サイングレード': 'Signature Grade',
            'ラベルタイプ': 'Label Type',
            'リバース認証/バーコード': 'Reverse Authentication/Barcode',
            'カテゴリ': 'Category',
            'バラエティ': 'Variety',
            '鑑定証明': 'Authentication Certificate',
            '主なサイン者名（2名以上）': 'Primary Signer Name (2 or more)',
            # 英文 -> 英文（保持一致性）
            'Certificate Number': 'Certificate Number',
            'Year': 'Year',
            'Brand/Title': 'Brand/Title',
            'Brand': 'Brand',
            'Title': 'Title',
            'Card Number': 'Card Number',
            'Subject': 'Subject',
            'Grade': 'Grade',
            'Signature Grade': 'Signature Grade',
            'Label Type': 'Label Type',
            'Reverse Authentication/Barcode': 'Reverse Authentication/Barcode',
            'Category': 'Category',
            'Variety': 'Variety',
            'Authentication Certificate': 'Authentication Certificate',
            'Primary Signer Name (2 or more)': 'Primary Signer Name (2 or more)',
        }
        
        # 查找包含Item Information相关关键词的script标签
        scripts = soup.find_all('script')
        for script in scripts:
            script_text = script.string or ''
            if not script_text or len(script_text) < 100:
                continue
            
            # 检查是否包含Item Information相关的关键词（日文或英文）
            has_item_info_keywords = any(
                keyword in script_text 
                for keyword in [
                    # 日文关键词
                    '証明番号', '発行年', 'ブランド', 'アイテム情報', 'cert-info',
                    # 英文关键词
                    'Certificate Number', 'Brand', 'Title', 'Year', 'Item Information',
                    'Card Number', 'Grade', 'Category', 'Variety'
                ]
            )
            
            if not has_item_info_keywords:
                continue
            
            # 尝试从Next.js序列化格式中提取数据
            # 格式: self.__next_f.push([1,"2d:[\"$\",\"div\",\"cert-info-0\",{...}])
            # 或者包含键值对的结构
            
            # 方法1: 解析cert-info结构
            # 注意：在script.string中，引号是双重转义的（\\"），所以需要匹配 \\" 或 "
            # 格式: "cert-info-N",{"children":[["$","dt",null,{"children":"字段名"}],["$","dd",null,{"children":"字段值"}]]}
            # 查找所有cert-info块，每个块包含一个dt（字段名）和一个dd（字段值）
            # 匹配转义的引号 \\" 或普通引号 "
            cert_info_pattern = r'cert-info-\d+.*?children(?:\\"|["\']):\s*\[\[.*?(?:\\"|["\'])dt(?:\\"|["\']).*?children(?:\\"|["\']):\s*(?:\\"|["\'])([^"\\]+)(?:\\"|["\']).*?(?:\\"|["\'])dd(?:\\"|["\']).*?children(?:\\"|["\']):\s*(?:\\"|["\'])([^"\\]+)(?:\\"|["\'])'
            cert_info_blocks = re.finditer(cert_info_pattern, script_text, re.DOTALL)
            
            for match in cert_info_blocks:
                field_name = match.group(1).strip()
                field_value = match.group(2).strip()
                
                if field_name and field_value and len(field_value) < 500 and field_value != '$L3c':
                    # 获取对应的英文字段名（如果字段名是日文，会映射到英文；如果是英文，保持不变）
                    en_key = field_mapping.get(field_name, field_name)
                    # 保存英文字段名
                    item_info[en_key] = field_value
                    # 如果字段名是日文，也保存日文键名（但排除 title 相关的日文字段）
                    if field_name != en_key and field_name not in ['ブランド／タイトル', 'タイトル']:
                        item_info[field_name] = field_value
            
            # 方法2: 更精确的模式匹配 - 匹配dt和dd的children
            # 格式: ["$","dt",null,{"children":"証明番号"}],["$","dd",null,{"children":"96098359"}
            # 或: ["$","dt",null,{"children":"Certificate Number"}],["$","dd",null,{"children":"96098359"}
            for field_key, en_key in field_mapping.items():
                # 跳过反向映射（避免重复处理）
                if field_key == en_key and field_key not in ['Certificate Number', 'Year', 'Brand/Title', 'Brand', 'Title', 'Card Number', 'Subject', 'Grade', 'Signature Grade', 'Label Type', 'Reverse Authentication/Barcode', 'Category', 'Variety', 'Authentication Certificate', 'Primary Signer Name (2 or more)']:
                    continue
                
                # 匹配模式: dt包含字段名，紧接着的dd包含字段值
                # 注意：引号可能是转义的 \\" 或普通的 "
                pattern = rf'(?:\\"|["\'])dt(?:\\"|["\']).*?children(?:\\"|["\']):\s*(?:\\"|["\']){re.escape(field_key)}(?:\\"|["\']).*?(?:\\"|["\'])dd(?:\\"|["\']).*?children(?:\\"|["\']):\s*(?:\\"|["\'])([^"\\]+)(?:\\"|["\'])'
                matches = re.finditer(pattern, script_text, re.DOTALL)
                for match in matches:
                    value = match.group(1).strip()
                    if value and len(value) < 500 and value != '$L3c':  # 排除特殊值
                        item_info[en_key] = value
                        # 如果字段名是日文，也保存日文键名（但排除 title 相关的日文字段）
                        if field_key != en_key and field_key not in ['ブランド／タイトル', 'タイトル']:
                            item_info[field_key] = value
                        break
        
        return item_info
    
    def _find_item_info_section(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """查找Item Information区域"""
        # 查找包含"Item Information"文本的元素
        for element in soup.find_all(['div', 'section', 'article', 'main']):
            text = element.get_text(strip=True)
            if 'item information' in text.lower() or 'item info' in text.lower():
                return element
        
        # 查找包含"Item Information"的标题
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if 'item information' in heading.get_text(strip=True).lower():
                # 返回标题后面的兄弟元素或父元素
                parent = heading.parent
                if parent:
                    return parent
                # 或者返回下一个兄弟元素
                next_sibling = heading.find_next_sibling()
                if next_sibling:
                    return next_sibling
        
        return None
    
    def _extract_from_section(self, section: BeautifulSoup) -> Dict[str, str]:
        """从找到的区域提取信息"""
        item_info = {}
        
        # 查找所有可能的键值对结构
        # 1. 表格结构
        tables = section.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        item_info[key] = value
        
        # 2. 定义列表结构 (dl)
        dl_elements = section.find_all('dl')
        for dl in dl_elements:
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True)
                value = dd.get_text(strip=True)
                if key and value:
                    item_info[key] = value
        
        # 3. 键值对文本模式 (Key: Value)
        text = section.get_text(separator='\n', strip=True)
        lines = text.split('\n')
        for line in lines:
            # 匹配 "Key: Value" 或 "Key - Value" 格式
            match = re.match(r'^([^:：\-]+)[:：\-]\s*(.+)$', line.strip())
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                if key and value and len(key) < 50:  # 避免误匹配
                    item_info[key] = value
        
        # 4. 查找包含特定字段名的元素
        field_names = [
            'brand', 'title', 'year', 'set', 'card number', 'card #',
            'player', 'team', 'variety', 'grade', 'certificate number',
            'cert #', 'serial number', 'serial #'
        ]
        
        for field_name in field_names:
            # 查找包含字段名的文本
            for element in section.find_all(['div', 'span', 'p', 'td', 'th', 'li']):
                text = element.get_text(strip=True)
                if field_name.lower() in text.lower():
                    # 尝试提取值
                    # 格式1: "Brand: Value"
                    match = re.search(
                        rf'{re.escape(field_name)}[:：]\s*([^\n]+)',
                        text,
                        re.IGNORECASE
                    )
                    if match:
                        item_info[field_name] = match.group(1).strip()
                    else:
                        # 格式2: 查找下一个兄弟元素
                        next_sibling = element.find_next_sibling()
                        if next_sibling:
                            value = next_sibling.get_text(strip=True)
                            if value:
                                item_info[field_name] = value
        
        return item_info
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict[str, str]:
        """从表格中提取Item Information"""
        item_info = {}
        
        # 查找所有表格
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    
                    # 检查是否是Item Information相关的字段
                    if key and value:
                        key_lower = key.lower()
                        # 常见字段名
                        if any(field in key_lower for field in [
                            'brand', 'title', 'year', 'set', 'card', 'player',
                            'team', 'variety', 'grade', 'certificate', 'serial'
                        ]):
                            item_info[key] = value
        
        return item_info
    
    def _extract_from_elements(self, soup: BeautifulSoup) -> Dict[str, str]:
        """从元素中提取Item Information"""
        item_info = {}
        
        # 查找包含常见字段名的元素
        field_patterns = {
            'brand': r'brand[:：]?\s*([^\n<]+)',
            'title': r'title[:：]?\s*([^\n<]+)',
            'year': r'year[:：]?\s*(\d{4})',
            'set': r'set[:：]?\s*([^\n<]+)',
            'card number': r'card\s*(?:number|#)[:：]?\s*([^\n<]+)',
            'player': r'player[:：]?\s*([^\n<]+)',
            'team': r'team[:：]?\s*([^\n<]+)',
            'grade': r'grade[:：]?\s*([^\n<]+)',
        }
        
        # 获取所有文本内容
        text_content = soup.get_text(separator='\n', strip=True)
        
        for field_name, pattern in field_patterns.items():
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                value = match.group(1).strip()
                if value and len(value) < 200:  # 避免匹配到过长的文本
                    item_info[field_name] = value
                    break  # 只取第一个匹配
        
        return item_info
    
    def get_brand_title(self, item_info: Dict[str, str]) -> Optional[str]:
        """
        从Item Information中提取Brand/Title
        
        Args:
            item_info: Item Information字典
            
        Returns:
            Brand/Title字符串，如果未找到则返回None
        """
        # 优先查找 "Brand/Title" 或 "Brand Title" 字段
        for key in item_info.keys():
            key_lower = key.lower()
            if 'brand' in key_lower and 'title' in key_lower:
                return item_info[key].strip()
        
        # 如果没找到，尝试分别查找Brand和Title，然后组合
        brand = None
        title = None
        
        for key, value in item_info.items():
            key_lower = key.lower()
            if 'brand' in key_lower and not brand:
                brand = value.strip()
            elif 'title' in key_lower and 'brand' not in key_lower and not title:
                title = value.strip()
        
        if brand and title:
            return f"{brand} {title}"
        elif brand:
            return brand
        elif title:
            return title
        
        return None
    
    def format_item_info_json(self, item_info: Dict[str, str]) -> str:
        """
        将Item Information字典格式化为JSON字符串
        
        Args:
            item_info: Item Information字典
            
        Returns:
            JSON格式的字符串
        """
        return json.dumps(item_info, ensure_ascii=False, indent=2)
    
    def save_item_info(self, item_info: Dict[str, str], save_path: Path, cert_number: str) -> Path:
        """
        保存Item Information到文件
        
        Args:
            item_info: Item Information字典
            save_path: 保存目录路径
            cert_number: 证书编号（用于文件名）
            
        Returns:
            保存的文件路径
        """
        # 确保保存目录存在
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 文件名使用证书编号
        filename = f"{cert_number}_item_info.json"
        file_path = save_path / filename
        
        # 保存为JSON格式
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(item_info, f, ensure_ascii=False, indent=2)
        
        return file_path
    
    def save_item_info_text(self, item_info: Dict[str, str], save_path: Path, cert_number: str) -> Path:
        """
        保存Item Information到文本文件（人类可读格式）
        
        Args:
            item_info: Item Information字典
            save_path: 保存目录路径
            cert_number: 证书编号（用于文件名）
            
        Returns:
            保存的文件路径
        """
        # 确保保存目录存在
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 文件名使用证书编号
        filename = f"{cert_number}_item_info.txt"
        file_path = save_path / filename
        
        # 保存为文本格式
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"PSA Certificate Item Information\n")
            f.write(f"Certificate Number: {cert_number}\n")
            f.write("=" * 80 + "\n\n")
            
            if item_info:
                for key, value in item_info.items():
                    f.write(f"{key}: {value}\n")
            else:
                f.write("No item information found.\n")
            
            f.write("\n" + "=" * 80 + "\n")
        
        return file_path

