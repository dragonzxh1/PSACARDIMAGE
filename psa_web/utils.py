import os
import re
import time
import random
import unicodedata
from urllib.parse import urlparse
from pathlib import Path


def sanitize_card_name(page_title: str) -> str:
    if not page_title:
        return "UnknownCard"
    card_name = page_title
    card_name = re.sub(r'^PSA\s+Certificate\s*#?\s*\d*\s*-?\s*', '', card_name, flags=re.IGNORECASE)
    card_name = re.sub(r'\s*[-|]\s*PSA.*$', '', card_name, flags=re.IGNORECASE)
    card_name = re.sub(r'#?\s*\d{6,}', '', card_name)
    card_name = card_name.strip()
    if not card_name or len(card_name) < 3:
        return "UnknownCard"
    card_name = re.sub(r'[<>:"/\\|?*]', '', card_name)
    card_name = re.sub(r'\s+', ' ', card_name).strip()
    card_name = card_name.replace(' ', '_')
    card_name = re.sub(r'_+', '_', card_name)
    if len(card_name) > 50:
        card_name = card_name[:50]
    card_name = card_name.strip('_')
    return card_name


def sanitize_filename(name: str, max_len: int = 120) -> str:
    if not isinstance(name, str):
        name = str(name) if name is not None else "file"
    name = unicodedata.normalize('NFKC', name)
    name = ''.join(ch for ch in name if ch.isprintable())
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip().replace(' ', '_')
    name = name.strip('._')
    if len(name) > max_len:
        name = name[:max_len].rstrip('._')
    return name or "file"


def fetch_with_retry(url: str, session, timeout=(5, 30), max_attempts: int = 3, verify: bool = True, headers: dict = None):
    import requests
    last_exc = None
    for attempt in range(max_attempts):
        try:
            time.sleep(0.05 + random.random() * 0.15)
            resp = session.get(url, timeout=timeout, stream=True, verify=verify, headers=headers or {})
            resp.raise_for_status()
            return resp
        except requests.exceptions.ConnectionError as e:
            # 连接错误：提供更清晰的错误信息
            error_msg = str(e)
            if "10061" in error_msg or "actively refused" in error_msg.lower() or "拒绝" in error_msg:
                last_exc = ConnectionError(f"无法连接到服务器 {url}：连接被拒绝（可能被防火墙阻止或服务器暂时不可用）")
            else:
                last_exc = ConnectionError(f"无法连接到服务器 {url}：{error_msg}")
            if attempt < max_attempts - 1:
                delay = 0.5 * (2 ** attempt) + random.uniform(0.5, 1.0)
                time.sleep(delay)
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                time.sleep(0.5 * (2 ** attempt) + random.uniform(0, 0.25))
    raise last_exc


def find_certificate_images(
    downloader,
    cert_number: str,
    target_size: str = 'large',
    card_name: str = None,
    brand_title: str = None,
    logger=None,
    max_images: int = 2
) -> tuple[list[tuple[str, str, str]], str, str]:
    """
    查找并选择证书的图片URL
    
    Args:
        downloader: PSACardImageDownloader 实例
        cert_number: 证书编号
        target_size: 目标图片尺寸 ('original', 'large', 'medium', 'small')
        card_name: 卡片名称（用于生成文件名），如果为None则从页面标题提取
        brand_title: Brand/Title（优先用于生成文件名），如果提供则优先使用
        logger: 日志记录器（可选）
        max_images: 最大返回图片数量，默认2（front/back）
    
    Returns:
        tuple: (图片列表, 提取的证书编号, 页面标题)
        图片列表格式: [(url, original_filename, unique_filename), ...]
    """
    # 提取证书编号
    extracted_num = downloader._extract_cert_number(cert_number)
    if logger:
        logger.info(f"提取的证书编号: {extracted_num} (原始输入: {cert_number})")
    
    # 获取预览URL（使用large尺寸获取列表）
    preview_urls, page_title = downloader.get_high_res_images(
        cert_number, 
        preview_mode=True, 
        image_size='large'
    )
    
    if logger:
        logger.info(f"找到 {len(preview_urls)} 个预览URL")
    
    if not preview_urls:
        if logger:
            logger.warning(f"证书 {extracted_num} 未找到任何图片")
        return [], extracted_num, page_title
    
    # 优先使用brand_title，如果没有则使用card_name，最后从页面标题提取
    if brand_title:
        card_name = sanitize_filename(brand_title, max_len=50)
        if logger:
            logger.info(f"使用Brand/Title作为文件名: {brand_title}")
    elif not card_name:
        card_name = sanitize_card_name(page_title)
        if card_name == "UnknownCard":
            card_name = f"Cert_{extracted_num}"
    
    # 转换URL到目标尺寸的函数
    def convert_url(u: str) -> str:
        original_url = u
        converted = downloader._convert_to_size(u, target_size)
        if not converted:
            # 如果转换失败，尝试手动移除尺寸路径
            converted = re.sub(r'/(?:small|large|medium|thumb)/', '/', u)
        result = (converted or u).rstrip('\\/').strip()
        if logger:
            logger.debug(f"[URL转换] 原始: {original_url}")
            logger.debug(f"[URL转换] 转换后: {result}")
        return result
    
    # 过滤和选择URL的函数
    seen_urls: set[str] = set()
    candidates: list[tuple[str, str, str]] = []
    
    def try_add(url_in: str):
        url_clean = url_in.rstrip('\\/').strip()
        if url_clean in seen_urls:
            return
        
        parsed = urlparse(url_clean)
        filename = os.path.basename(parsed.path).rstrip('\\/')
        if not filename or '.' not in filename:
            filename = f"unknown_{len(candidates)}.jpg"
        
        filename_lower = filename.lower()
        exclude_keywords = [
            'table-image', 'certified', 'logo', 'icon', 'button', 'badge',
            'avatar', 'spinner', 'loading', 'placeholder',
            'og-meta', 'meta', 'og-image', 'social', 'share'
        ]
        if any(keyword in filename_lower for keyword in exclude_keywords):
            return
        
        url_lower = url_clean.lower()
        if '/meta/' in url_lower or '/social/' in url_lower:
            return
        
        file_ext = (os.path.splitext(filename)[1] or '.jpg').lower()
        suffix_letter = chr(ord('A') + len(candidates))
        # 使用brand_title时，格式为: brand_title_A, brand_title_B
        # 注意：这里brand_title在外部作用域，可以直接访问
        if brand_title:
            safe_base = sanitize_filename(f"{card_name}_{suffix_letter}", max_len=100)
        else:
            safe_base = sanitize_filename(f"{card_name}PSA_{suffix_letter}")
        unique_filename = f"{safe_base}{file_ext}"
        candidates.append((url_clean, filename, unique_filename))
        seen_urls.add(url_clean)
    
    # 优先选择front/back
    front_like = [u for u in preview_urls if re.search(r'/(front|obv|obverse)\b', u, re.I)]
    back_like = [u for u in preview_urls if re.search(r'/(back|rev|reverse)\b', u, re.I)]
    
    if front_like:
        try_add(front_like[0])
    if back_like and len(candidates) < max_images:
        try_add(back_like[0])
    
    # 不足则从其余URL补齐
    if len(candidates) < max_images:
        for u in preview_urls:
            if len(candidates) >= max_images:
                break
            try_add(u)
    
    if logger:
        logger.info(f"初步选择 {len(candidates)} 个候选URL")
    
    # 转换到目标尺寸并去重
    # 重要：先转换所有URL，再去重，最后生成文件名，确保每个唯一的转换后URL只有一个文件名
    converted_candidates: list[tuple[str, str, str]] = []
    seen_converted: set[str] = set()
    
    # 先转换已选中的candidates，但先不生成文件名
    converted_urls_from_candidates: list[str] = []
    for url_preview, filename_original, _ in candidates:
        converted_url = convert_url(url_preview)
        if logger:
            logger.info(f"[转换] 预览URL: {url_preview}")
            logger.info(f"[转换] 转换后URL: {converted_url}")
        
        if converted_url and converted_url not in seen_converted:
            converted_urls_from_candidates.append(converted_url)
            seen_converted.add(converted_url)
            if logger:
                logger.info(f"[转换] ✓ 添加唯一URL: {converted_url}")
        elif converted_url in seen_converted:
            if logger:
                logger.warning(f"[转换] ✗ 转换后URL重复，跳过: {converted_url} (原始: {url_preview})")
    
    # 如果转换后数量不足，尝试从剩余预览URL中补齐
    if len(converted_urls_from_candidates) < max_images:
        if logger:
            logger.info(f"转换后只有 {len(converted_urls_from_candidates)} 个唯一URL，尝试补齐")
        for u in preview_urls:
            if len(converted_urls_from_candidates) >= max_images:
                break
            if u in {c[0] for c in candidates}:
                continue
            
            u_conv = convert_url(u)
            if u_conv and u_conv not in seen_converted:
                converted_urls_from_candidates.append(u_conv)
                seen_converted.add(u_conv)
                if logger:
                    logger.info(f"从剩余URL补齐: {u} -> {u_conv}")
            elif u_conv in seen_converted:
                if logger:
                    logger.debug(f"预览URL转换后重复，跳过: {u} -> {u_conv}")
    
    # 现在为每个唯一的转换后URL生成文件名
    for idx, converted_url in enumerate(converted_urls_from_candidates):
        parsed = urlparse(converted_url)
        filename_original = os.path.basename(parsed.path).rstrip('\\/')
        if not filename_original or '.' not in filename_original:
            filename_original = f"unknown_{idx}.jpg"
        
        file_ext = (os.path.splitext(filename_original)[1] or '.jpg').lower()
        suffix_letter = chr(ord('A') + idx)
        # 使用brand_title时，格式为: brand_title_A, brand_title_B
        if brand_title:
            safe_base = sanitize_filename(f"{card_name}_{suffix_letter}", max_len=100)
        else:
            safe_base = sanitize_filename(f"{card_name}PSA_{suffix_letter}")
        unique_filename = f"{safe_base}{file_ext}"
        
        converted_candidates.append((converted_url, filename_original, unique_filename))
        if logger:
            logger.info(f"为转换后URL生成文件名: {converted_url} -> {unique_filename}")
    
    if logger:
        logger.info(f"最终返回 {len(converted_candidates)} 个唯一图片URL（目标尺寸: {target_size}）")
    
    return converted_candidates, extracted_num, page_title

