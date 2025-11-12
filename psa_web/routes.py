from flask import Blueprint, jsonify, render_template, request, current_app, send_file
from pathlib import Path
from urllib.parse import urlparse
import re
import zipfile
import os
import time
import random
import pandas as pd
from werkzeug.utils import secure_filename

from .utils import sanitize_card_name, sanitize_filename, fetch_with_retry, find_certificate_images
from psa_item_info_extractor import PSAItemInfoExtractor


api_bp = Blueprint('api', __name__)
page_bp = Blueprint('pages', __name__)


@page_bp.route('/')
def index():
    return render_template('index.html')


def _parse_cert_numbers_from_file(upload_path: Path) -> list[str]:
    cert_numbers: list[str] = []
    suffix = upload_path.suffix.lower()
    if suffix == '.txt':
        try:
            with open(upload_path, 'r', encoding='utf-8') as f:
                for line in f:
                    value = line.strip()
                    if value:
                        cert_numbers.append(value)
        except UnicodeDecodeError:
            with open(upload_path, 'r', encoding='latin-1') as f:
                for line in f:
                    value = line.strip()
                    if value:
                        cert_numbers.append(value)
    elif suffix in ('.xlsx', '.xls'):
        df = pd.read_excel(upload_path, dtype=str, header=None)
        for row in df.values.tolist():
            for cell in row:
                if isinstance(cell, str):
                    value = cell.strip()
                    if value:
                        cert_numbers.append(value)
                elif cell is not None and not (isinstance(cell, float) and pd.isna(cell)):
                    cert_numbers.append(str(cell).strip())
    return [cn for cn in cert_numbers if isinstance(cn, str) and cn.strip()]


@api_bp.route('/batch_download', methods=['POST'])
def batch_download_images():
    try:
        language = request.form.get('language', 'en')
        image_size = (request.form.get('image_size') or 'original').strip().lower()
        valid_sizes = ['original', 'large', 'medium', 'small']
        if image_size not in valid_sizes:
            image_size = 'original'

        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file provided' if language == 'en' else '未提供文件'
            }), 400

        file_storage = request.files['file']
        if file_storage.filename == '':
            return jsonify({
                'success': False,
                'message': 'Empty filename' if language == 'en' else '文件名为空'
            }), 400

        temp_dir: Path = current_app.config['DOWNLOAD_DIR'] / 'tmp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        safe_name = secure_filename(file_storage.filename)
        upload_path = temp_dir / safe_name
        file_storage.save(upload_path)

        cert_numbers = _parse_cert_numbers_from_file(upload_path)
        try:
            upload_path.unlink(missing_ok=True)
        except Exception:
            pass

        if not cert_numbers:
            return jsonify({
                'success': False,
                'message': 'No certificate numbers found in file' if language == 'en' else '文件中未找到证书编号'
            }), 400

        # 复用与 /api/download 相同的下载流程
        downloader = current_app.config['DOWNLOADER']
        download_dir: Path = current_app.config['DOWNLOAD_DIR']
        
        # 初始化Item Information提取器
        item_info_extractor = PSAItemInfoExtractor()

        all_image_urls = {}
        cert_info = {}
        all_downloaded_files = []
        total_success_count = 0
        success_certs = 0
        failed_certs = 0
        # 收集下载日志信息
        download_log = []

        current_app.logger.info(f"[Batch] ========== 开始批量下载 ==========")
        current_app.logger.info(f"[Batch] 证书总数: {len(cert_numbers)}")
        current_app.logger.info(f"[Batch] 证书列表: {cert_numbers}")
        current_app.logger.info(f"[Batch] 图片尺寸: {image_size}")

        for cert_num in cert_numbers:
            if not isinstance(cert_num, str) or not cert_num.strip():
                failed_certs += 1
                continue
            current_app.logger.info(f"[Batch] 证书编号: {cert_num}, 目标尺寸: {image_size}")
            try:
                # 获取页面HTML以提取Item Information
                extracted_num = downloader._extract_cert_number(cert_num)
                html = downloader._get_page_html(extracted_num)
                item_info = item_info_extractor.extract_item_info(html)
                brand_title = item_info_extractor.get_brand_title(item_info)
                
                # 保存Item Information文件
                save_path = download_dir / f"PSA_{extracted_num}"
                save_path.mkdir(parents=True, exist_ok=True)
                item_info_file = item_info_extractor.save_item_info_text(item_info, save_path, extracted_num)
                current_app.logger.info(f"[Batch] Item Information已保存: {item_info_file}")
                
                # 直接获取目标尺寸的图片列表，避免重复调用
                image_list, extracted_num, page_title = find_certificate_images(
                    downloader=downloader,
                    cert_number=cert_num,
                    target_size=image_size,  # 直接使用请求的尺寸
                    brand_title=brand_title,  # 使用brand title作为文件名
                    logger=current_app.logger,
                    max_images=10  # 下载所有找到的图片
                )
                
                if not image_list:
                    current_app.logger.warning(f"[Batch] 证书 {extracted_num} 未找到任何图片（尺寸: {image_size}）")
                    all_image_urls[extracted_num] = []
                    cert_info[extracted_num] = {'title': page_title, 'original': cert_num}
                    # 记录未找到图片
                    download_log.append({
                        'cert_number': extracted_num,
                        'original_cert': cert_num,
                        'title': page_title,
                        'url': '',
                        'original_filename': '',
                        'saved_filename': '',
                        'status': 'no_images',
                        'error': f'No images found for size: {image_size}'
                    })
                    failed_certs += 1
                    continue

                # 优化：如果请求的尺寸就是 large，直接使用 image_list 作为预览
                if image_size == 'large':
                    preview_urls = [url for url, _, _ in image_list]
                else:
                    # 只获取预览URL，不进行完整的图片查找和转换
                    preview_urls_raw, _ = downloader.get_high_res_images(
                        cert_num,
                        preview_mode=True,
                        image_size='large'
                    )
                    # 简单转换到 large 尺寸用于预览
                    preview_urls = []
                    seen_preview = set()
                    for preview_url in preview_urls_raw[:10]:  # 限制数量
                        large_url = downloader._convert_to_size(preview_url, 'large')
                        if large_url:
                            large_url = large_url.rstrip('\\/').strip()
                            if large_url not in seen_preview:
                                preview_urls.append(large_url)
                                seen_preview.add(large_url)
                
                all_image_urls[extracted_num] = preview_urls
                cert_info[extracted_num] = {'title': page_title, 'original': cert_num}
                
                current_app.logger.info(f"[Batch] 证书 {extracted_num} 找到 {len(image_list)} 张图片（尺寸: {image_size}）")
                for idx, (url, _, filename) in enumerate(image_list, 1):
                    current_app.logger.info(f"[Batch] 图片 {idx}: {url} -> {filename}")

                current_app.logger.info(f"[Batch] 证书 {extracted_num} 开始下载 {len(image_list)} 张图片（尺寸: {image_size}）")
                success_count_for_cert = 0
                
                for url, original_filename, unique_filename in image_list:
                    try:
                        # 记录下载信息，用于调试
                        current_app.logger.info(f"[Batch] 准备下载: URL={url}, 保存为={unique_filename}")
                        
                        referer = f"https://www.psacard.com/cert/{extracted_num}"
                        response = fetch_with_retry(
                            url,
                            downloader.session,
                            timeout=(5, 30),
                            max_attempts=3,
                            verify=downloader.verify_ssl,
                            headers={'Referer': referer}
                        )
                        file_path = save_path / unique_filename
                        
                        # 如果文件已存在，先删除（避免使用旧文件）
                        if file_path.exists():
                            current_app.logger.warning(f"[Batch] 文件已存在，将覆盖: {file_path}")
                            file_path.unlink()
                        
                        # 下载并保存文件
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # 验证文件是否成功保存
                        if file_path.exists() and file_path.stat().st_size > 0:
                            file_size = file_path.stat().st_size
                            current_app.logger.info(f"[Batch] 文件下载成功: {unique_filename}, 大小={file_size} 字节, URL={url}")
                            all_downloaded_files.append(file_path)
                            success_count_for_cert += 1
                            total_success_count += 1
                            # 记录成功下载
                            download_log.append({
                                'cert_number': extracted_num,
                                'original_cert': cert_num,
                                'title': page_title,
                                'url': url,
                                'original_filename': original_filename,
                                'saved_filename': unique_filename,
                                'status': 'success',
                                'file_path': str(file_path.relative_to(download_dir))
                            })
                        else:
                            # 记录下载失败
                            current_app.logger.error(f"[Batch] 文件保存失败或文件为空: {file_path}")
                            download_log.append({
                                'cert_number': extracted_num,
                                'original_cert': cert_num,
                                'title': page_title,
                                'url': url,
                                'original_filename': original_filename,
                                'saved_filename': unique_filename,
                                'status': 'failed',
                                'error': 'File not found or empty after download'
                            })
                    except Exception as e:
                        current_app.logger.error(f"[Batch] Download failed {url}: {str(e)}", exc_info=True)
                        # 记录下载失败
                        download_log.append({
                            'cert_number': extracted_num,
                            'original_cert': cert_num,
                            'title': page_title,
                            'url': url,
                            'original_filename': original_filename if 'original_filename' in locals() else 'unknown',
                            'saved_filename': unique_filename if 'unique_filename' in locals() else 'unknown',
                            'status': 'failed',
                            'error': str(e)
                        })
                        continue

                if success_count_for_cert > 0:
                    success_certs += 1
                    current_app.logger.info(f"[Batch] 证书 {extracted_num} 处理完成: 成功下载 {success_count_for_cert} 张图片")
                else:
                    failed_certs += 1
                    current_app.logger.warning(f"[Batch] 证书 {extracted_num} 处理完成: 未下载任何图片")

            except Exception as e:
                current_app.logger.error(f"[Batch] Error processing certificate {cert_num}: {str(e)}", exc_info=True)
                try:
                    extracted_num = downloader._extract_cert_number(cert_num)
                except:
                    extracted_num = cert_num
                all_image_urls[extracted_num] = []
                cert_info[extracted_num] = {'title': f'Error: {str(e)}', 'original': cert_num}
                # 记录处理错误
                download_log.append({
                    'cert_number': extracted_num,
                    'original_cert': cert_num,
                    'title': f'Error: {str(e)}',
                    'url': '',
                    'original_filename': '',
                    'saved_filename': '',
                    'status': 'error',
                    'error': str(e)
                })
                failed_certs += 1
                continue

        if total_success_count == 0:
            current_app.logger.error(f"[Batch] ========== 批量下载失败总结 ==========")
            current_app.logger.error(f"[Batch] 总证书数: {len(cert_numbers)}")
            current_app.logger.error(f"[Batch] 成功证书数: {success_certs}")
            current_app.logger.error(f"[Batch] 失败证书数: {failed_certs}")
            current_app.logger.error(f"[Batch] 成功下载图片数: {total_success_count}")
            current_app.logger.error(f"[Batch] 证书编号列表: {cert_numbers}")
            current_app.logger.error(f"[Batch] 所有证书的图片URL: {all_image_urls}")
            current_app.logger.error(f"[Batch] 证书信息: {cert_info}")
            current_app.logger.error(f"[Batch] ========================================")
            return jsonify({
                'success': False,
                'message': 'Failed to download images for all certificates' if language == 'en' else '所有证书的图片下载失败',
                'total_certs': len(cert_numbers),
                'success_certs': success_certs,
                'failed_certs': failed_certs
            }), 500

        current_app.logger.info(f"[Batch] ========== 批量下载处理完成 ==========")
        current_app.logger.info(f"[Batch] 总证书数: {len(cert_numbers)}")
        current_app.logger.info(f"[Batch] 成功证书数: {success_certs}")
        current_app.logger.info(f"[Batch] 失败证书数: {failed_certs}")
        current_app.logger.info(f"[Batch] 成功下载图片数: {total_success_count}")
        current_app.logger.info(f"[Batch] 准备创建ZIP文件...")

        timestamp = int(time.time())
        zip_path = current_app.config['DOWNLOAD_DIR'] / f"PSA_batch_{timestamp}.zip"
        zip_filename = f"PSA_batch_{timestamp}.zip"

        # 生成日志文件
        log_filename = f"download_log_{timestamp}.txt"
        log_path = current_app.config['DOWNLOAD_DIR'] / log_filename
        
        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write("=" * 80 + "\n")
            log_file.write("PSA Certificate Download Log\n")
            log_file.write("=" * 80 + "\n\n")
            log_file.write(f"Download Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}\n")
            log_file.write(f"Image Size: {image_size}\n")
            log_file.write(f"Total Certificates: {len(cert_numbers)}\n")
            log_file.write(f"Success Certificates: {success_certs}\n")
            log_file.write(f"Failed Certificates: {failed_certs}\n")
            log_file.write(f"Total Images Downloaded: {total_success_count}\n")
            log_file.write("\n" + "=" * 80 + "\n")
            log_file.write("Download Details\n")
            log_file.write("=" * 80 + "\n\n")
            
            for idx, entry in enumerate(download_log, 1):
                log_file.write(f"\n[{idx}] Certificate: {entry['cert_number']}\n")
                log_file.write(f"    Original Input: {entry['original_cert']}\n")
                log_file.write(f"    Title: {entry['title']}\n")
                log_file.write(f"    Status: {entry['status']}\n")
                if entry['url']:
                    log_file.write(f"    URL: {entry['url']}\n")
                if entry['original_filename']:
                    log_file.write(f"    Original Filename: {entry['original_filename']}\n")
                if entry['saved_filename']:
                    log_file.write(f"    Saved Filename: {entry['saved_filename']}\n")
                if entry.get('file_path'):
                    log_file.write(f"    File Path: {entry['file_path']}\n")
                if entry.get('error'):
                    log_file.write(f"    Error: {entry['error']}\n")
                log_file.write("-" * 80 + "\n")
        
        current_app.logger.info(f"[Batch] 日志文件已生成: {log_path}")
        
        # 收集所有Item Information文件
        item_info_files = []
        for cert_num in cert_numbers:
            try:
                extracted_num = downloader._extract_cert_number(cert_num)
                item_info_path = download_dir / f"PSA_{extracted_num}" / f"{extracted_num}_item_info.txt"
                if item_info_path.exists():
                    item_info_files.append(item_info_path)
                    current_app.logger.info(f"[Batch] 找到Item Information文件: {item_info_path}")
            except:
                pass
        
        # 将图片文件、Item Information文件和日志文件添加到ZIP中
        current_app.logger.info(f"[Batch] 准备创建ZIP文件（包含 {len(all_downloaded_files)} 个图片文件、{len(item_info_files)} 个Item Information文件和日志文件）...")
        
        # 去重：使用集合跟踪已添加的文件路径（避免重复添加）
        added_to_zip = set()
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加所有下载的图片文件
            for file_path in all_downloaded_files:
                try:
                    if file_path.exists():
                        # 使用相对路径作为ZIP中的文件名，保持目录结构
                        # 例如: PSA_96098359/PSA_A.jpg
                        arcname = str(file_path.relative_to(download_dir))
                        
                        # 检查是否已添加（避免重复）
                        if arcname in added_to_zip:
                            current_app.logger.warning(f"[Batch] 文件已在ZIP中，跳过: {arcname}")
                            continue
                        
                        # 获取文件大小用于验证
                        file_size = file_path.stat().st_size
                        current_app.logger.info(f"[Batch] 添加文件到ZIP: {arcname} (大小: {file_size} 字节)")
                        
                        zipf.write(file_path, arcname)
                        added_to_zip.add(arcname)
                    else:
                        current_app.logger.warning(f"[Batch] 文件不存在，跳过: {file_path}")
                except Exception as e:
                    current_app.logger.error(f"[Batch] Failed writing {file_path} to ZIP: {e}")
            
            # 添加所有Item Information文件
            for item_info_path in item_info_files:
                try:
                    if item_info_path.exists():
                        arcname = str(item_info_path.relative_to(download_dir))
                        if arcname not in added_to_zip:
                            zipf.write(item_info_path, arcname)
                            added_to_zip.add(arcname)
                            current_app.logger.info(f"[Batch] Item Information文件已添加到ZIP: {arcname}")
                except Exception as e:
                    current_app.logger.error(f"[Batch] Failed writing Item Information {item_info_path} to ZIP: {e}")
            
            # 添加日志文件
            try:
                zipf.write(log_path, log_filename)
                current_app.logger.info(f"[Batch] 日志文件已添加到ZIP: {log_filename}")
            except Exception as e:
                current_app.logger.error(f"[Batch] Failed writing log to ZIP: {e}")
        
        # 删除临时日志文件（可选，保留也可以）
        # log_path.unlink()

        current_app.logger.info(f"[Batch] ZIP文件创建完成: {zip_path}")
        current_app.logger.info(f"[Batch] ========================================")

        return jsonify({
            'success': True,
            'message': f'Batch downloaded {total_success_count} image(s) from {len(cert_numbers)} certificate(s)' if language == 'en'
                      else f'批量下载完成：从 {len(cert_numbers)} 个证书下载了 {total_success_count} 张图片',
            'image_urls': all_image_urls,
            'cert_info': cert_info,
            'download_url': f'/api/download_file/{zip_filename}',
            'total_certs': len(cert_numbers),
            'success_certs': success_certs,
            'failed_certs': failed_certs
        })
    except Exception as e:
        current_app.logger.error(f"[Batch] ========== 批量下载发生未捕获异常 ==========")
        current_app.logger.error(f"[Batch] 错误类型: {type(e).__name__}")
        current_app.logger.error(f"[Batch] 错误消息: {str(e)}", exc_info=True)
        import traceback
        current_app.logger.error(f"[Batch] 完整堆栈跟踪:\n{traceback.format_exc()}")
        current_app.logger.error(f"[Batch] ==============================================")
        language = request.form.get('language', 'en') if request.form else 'en'
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}' if language == 'en' else f'发生错误: {str(e)}'
        }), 500

@api_bp.route('/download', methods=['POST'])
def download_images():
    try:
        data = request.get_json()
        language = data.get('language', 'en')
        image_size = data.get('image_size', 'original').strip().lower()

        cert_numbers = data.get('cert_numbers', [])
        cert_number = data.get('cert_number', '').strip()
        if not cert_numbers and cert_number:
            cert_numbers = [cert_number]
        elif cert_numbers and isinstance(cert_numbers, str):
            cert_numbers = [cn.strip() for cn in cert_numbers.split('+') if cn.strip()]

        if not cert_numbers:
            return jsonify({
                'success': False,
                'message': 'Certificate number is required' if language == 'en' else '请输入证书编号'
            }), 400

        valid_sizes = ['original', 'large', 'medium', 'small']
        if image_size not in valid_sizes:
            image_size = 'original'

        current_app.logger.info(f"[Download] 请求的图片尺寸: {image_size}")

        downloader = current_app.config['DOWNLOADER']
        download_dir: Path = current_app.config['DOWNLOAD_DIR']
        
        # 初始化Item Information提取器
        item_info_extractor = PSAItemInfoExtractor()

        all_image_urls = {}
        cert_info = {}
        all_downloaded_files = []
        total_success_count = 0
        # 收集下载日志信息
        download_log = []

        for cert_num in cert_numbers:
            if not cert_num.strip():
                continue
            current_app.logger.info(f"[Download] 证书编号: {cert_num}, 目标尺寸: {image_size}")
            try:
                # 获取页面HTML以提取Item Information
                extracted_num = downloader._extract_cert_number(cert_num)
                html = downloader._get_page_html(extracted_num)
                item_info = item_info_extractor.extract_item_info(html)
                brand_title = item_info_extractor.get_brand_title(item_info)
                
                # 保存Item Information文件
                save_path = download_dir / f"PSA_{extracted_num}"
                save_path.mkdir(parents=True, exist_ok=True)
                item_info_file = item_info_extractor.save_item_info_text(item_info, save_path, extracted_num)
                current_app.logger.info(f"[Download] Item Information已保存: {item_info_file}")
                
                # 直接获取目标尺寸的图片列表，避免重复调用
                image_list, extracted_num, page_title = find_certificate_images(
                    downloader=downloader,
                    cert_number=cert_num,
                    target_size=image_size,  # 直接使用请求的尺寸
                    brand_title=brand_title,  # 使用brand title作为文件名
                    logger=current_app.logger,
                    max_images=10  # 下载所有找到的图片
                )
                
                if not image_list:
                    current_app.logger.warning(f"[Download] 证书 {extracted_num} 未找到任何图片（尺寸: {image_size}）")
                    all_image_urls[extracted_num] = []
                    cert_info[extracted_num] = {'title': page_title, 'original': cert_num}
                    # 记录未找到图片
                    download_log.append({
                        'cert_number': extracted_num,
                        'original_cert': cert_num,
                        'title': page_title,
                        'url': '',
                        'original_filename': '',
                        'saved_filename': '',
                        'status': 'no_images',
                        'error': f'No images found for size: {image_size}'
                    })
                    continue

                # 优化：如果请求的尺寸就是 large，直接使用 image_list 作为预览
                if image_size == 'large':
                    preview_urls = [url for url, _, _ in image_list]
                else:
                    # 只获取预览URL，不进行完整的图片查找和转换
                    preview_urls_raw, _ = downloader.get_high_res_images(
                        cert_num,
                        preview_mode=True,
                        image_size='large'
                    )
                    # 简单转换到 large 尺寸用于预览
                    preview_urls = []
                    seen_preview = set()
                    for preview_url in preview_urls_raw[:10]:  # 限制数量
                        large_url = downloader._convert_to_size(preview_url, 'large')
                        if large_url:
                            large_url = large_url.rstrip('\\/').strip()
                            if large_url not in seen_preview:
                                preview_urls.append(large_url)
                                seen_preview.add(large_url)
                
                all_image_urls[extracted_num] = preview_urls
                cert_info[extracted_num] = {'title': page_title, 'original': cert_num}
                
                current_app.logger.info(f"[Download] 证书 {extracted_num} 找到 {len(image_list)} 张图片（尺寸: {image_size}）")
                for idx, (url, _, filename) in enumerate(image_list, 1):
                    current_app.logger.info(f"[Download] 图片 {idx}: {url} -> {filename}")

                current_app.logger.info(f"下载证书 {extracted_num} 的 {len(image_list)} 张图片（尺寸: {image_size}）")
                success_count = 0

                for i, (url, original_filename, unique_filename) in enumerate(image_list, 1):
                    url = url.rstrip('\\/').strip()
                    current_app.logger.info(f"[Download] 准备下载: URL={url}, 保存为={unique_filename}")
                    try:
                        referer = f"https://www.psacard.com/cert/{extracted_num}"
                        response = fetch_with_retry(
                            url,
                            downloader.session,
                            timeout=(5, 30),
                            max_attempts=3,
                            verify=downloader.verify_ssl,
                            headers={'Referer': referer}
                        )
                        file_path = save_path / unique_filename
                        
                        # 如果文件已存在，先删除（避免使用旧文件）
                        if file_path.exists():
                            current_app.logger.warning(f"[Download] 文件已存在，将覆盖: {file_path}")
                            file_path.unlink()
                        
                        # 下载并保存文件
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # 验证文件是否成功保存
                        if file_path.exists() and file_path.stat().st_size > 0:
                            file_size = file_path.stat().st_size
                            current_app.logger.info(f"[Download] 文件下载成功: {unique_filename}, 大小={file_size} 字节, URL={url}")
                            all_downloaded_files.append(file_path)
                            success_count += 1
                            total_success_count += 1
                            # 记录成功下载
                            download_log.append({
                                'cert_number': extracted_num,
                                'original_cert': cert_num,
                                'title': page_title,
                                'url': url,
                                'original_filename': original_filename,
                                'saved_filename': unique_filename,
                                'status': 'success',
                                'file_path': str(file_path.relative_to(download_dir))
                            })
                        else:
                            # 记录下载失败
                            current_app.logger.error(f"[Download] 文件保存失败或文件为空: {file_path}")
                            download_log.append({
                                'cert_number': extracted_num,
                                'original_cert': cert_num,
                                'title': page_title,
                                'url': url,
                                'original_filename': original_filename,
                                'saved_filename': unique_filename,
                                'status': 'failed',
                                'error': 'File not found or empty after download'
                            })
                    except Exception as e:
                        current_app.logger.error(f"下载失败 {url}: {str(e)}", exc_info=True)
                        # 记录下载失败
                        download_log.append({
                            'cert_number': extracted_num,
                            'original_cert': cert_num,
                            'title': page_title,
                            'url': url,
                            'original_filename': original_filename if 'original_filename' in locals() else 'unknown',
                            'saved_filename': unique_filename if 'unique_filename' in locals() else 'unknown',
                            'status': 'failed',
                            'error': str(e)
                        })
                        continue

                current_app.logger.info(f"证书 {extracted_num} 下载完成: {success_count}/{len(image_list)} 成功")

            except Exception as e:
                current_app.logger.error(f"处理证书 {cert_num} 时出错: {str(e)}", exc_info=True)
                try:
                    extracted_num = downloader._extract_cert_number(cert_num)
                except:
                    extracted_num = cert_num
                all_image_urls[extracted_num] = []
                cert_info[extracted_num] = {'title': f'Error: {str(e)}', 'original': cert_num}
                # 记录处理错误
                download_log.append({
                    'cert_number': extracted_num,
                    'original_cert': cert_num,
                    'title': f'Error: {str(e)}',
                    'url': '',
                    'original_filename': '',
                    'saved_filename': '',
                    'status': 'error',
                    'error': str(e)
                })
                continue

        if total_success_count == 0:
            return jsonify({
                'success': False,
                'message': 'Failed to download images for all certificates' if language == 'en' else '所有证书的图片下载失败'
            }), 500

        if len(cert_numbers) == 1:
            cert_num = downloader._extract_cert_number(cert_numbers[0])
            zip_path = current_app.config['DOWNLOAD_DIR'] / f"PSA_{cert_num}.zip"
            zip_filename = f"PSA_{cert_num}.zip"
            timestamp = int(time.time())
        else:
            timestamp = int(time.time())
            zip_path = current_app.config['DOWNLOAD_DIR'] / f"PSA_batch_{timestamp}.zip"
            zip_filename = f"PSA_batch_{timestamp}.zip"

        # 生成日志文件
        log_filename = f"download_log_{timestamp}.txt"
        log_path = current_app.config['DOWNLOAD_DIR'] / log_filename
        
        # 按证书统计成功和失败数量
        cert_status = {}
        for entry in download_log:
            cert_num = entry['cert_number']
            if cert_num not in cert_status:
                cert_status[cert_num] = {'has_success': False, 'has_failed': False}
            if entry['status'] == 'success' and entry.get('url'):
                cert_status[cert_num]['has_success'] = True
            elif entry['status'] in ['failed', 'error', 'no_images']:
                cert_status[cert_num]['has_failed'] = True
        
        success_certs = sum(1 for status in cert_status.values() if status['has_success'])
        failed_certs = sum(1 for status in cert_status.values() if status['has_failed'] and not status['has_success'])
        
        with open(log_path, 'w', encoding='utf-8') as log_file:
            log_file.write("=" * 80 + "\n")
            log_file.write("PSA Certificate Download Log\n")
            log_file.write("=" * 80 + "\n\n")
            log_file.write(f"Download Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}\n")
            log_file.write(f"Image Size: {image_size}\n")
            log_file.write(f"Total Certificates: {len(cert_numbers)}\n")
            log_file.write(f"Success Certificates: {success_certs}\n")
            log_file.write(f"Failed Certificates: {failed_certs}\n")
            log_file.write(f"Total Images Downloaded: {total_success_count}\n")
            log_file.write("\n" + "=" * 80 + "\n")
            log_file.write("Download Details\n")
            log_file.write("=" * 80 + "\n\n")
            
            for idx, entry in enumerate(download_log, 1):
                log_file.write(f"\n[{idx}] Certificate: {entry['cert_number']}\n")
                log_file.write(f"    Original Input: {entry['original_cert']}\n")
                log_file.write(f"    Title: {entry['title']}\n")
                log_file.write(f"    Status: {entry['status']}\n")
                if entry['url']:
                    log_file.write(f"    URL: {entry['url']}\n")
                if entry['original_filename']:
                    log_file.write(f"    Original Filename: {entry['original_filename']}\n")
                if entry['saved_filename']:
                    log_file.write(f"    Saved Filename: {entry['saved_filename']}\n")
                if entry.get('file_path'):
                    log_file.write(f"    File Path: {entry['file_path']}\n")
                if entry.get('error'):
                    log_file.write(f"    Error: {entry['error']}\n")
                log_file.write("-" * 80 + "\n")
        
        current_app.logger.info(f"日志文件已生成: {log_path}")
        
        # 将图片文件和日志文件添加到ZIP中
        current_app.logger.info(f"准备创建ZIP文件（包含 {len(all_downloaded_files)} 个图片文件和日志文件）...")
        # 收集所有Item Information文件
        item_info_files = []
        for cert_num in cert_numbers:
            try:
                extracted_num = downloader._extract_cert_number(cert_num)
                item_info_path = download_dir / f"PSA_{extracted_num}" / f"{extracted_num}_item_info.txt"
                if item_info_path.exists():
                    item_info_files.append(item_info_path)
                    current_app.logger.info(f"[Download] 找到Item Information文件: {item_info_path}")
            except:
                pass
        
        # 去重：使用集合跟踪已添加的文件路径（避免重复添加）
        added_to_zip = set()
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加所有下载的图片文件
            for file_path in all_downloaded_files:
                try:
                    if file_path.exists():
                        # 使用相对路径作为ZIP中的文件名，保持目录结构
                        # 例如: PSA_96098359/PSA_A.jpg
                        arcname = str(file_path.relative_to(download_dir))
                        
                        # 检查是否已添加（避免重复）
                        if arcname in added_to_zip:
                            current_app.logger.warning(f"[Download] 文件已在ZIP中，跳过: {arcname}")
                            continue
                        
                        # 获取文件大小用于验证
                        file_size = file_path.stat().st_size
                        current_app.logger.info(f"[Download] 添加文件到ZIP: {arcname} (大小: {file_size} 字节)")
                        
                        zipf.write(file_path, arcname)
                        added_to_zip.add(arcname)
                    else:
                        current_app.logger.warning(f"[Download] 文件不存在，跳过: {file_path}")
                except Exception as e:
                    current_app.logger.error(f"[Download] Failed writing {file_path} to ZIP: {e}")
            
            # 添加所有Item Information文件
            for item_info_path in item_info_files:
                try:
                    if item_info_path.exists():
                        arcname = str(item_info_path.relative_to(download_dir))
                        if arcname not in added_to_zip:
                            zipf.write(item_info_path, arcname)
                            added_to_zip.add(arcname)
                            current_app.logger.info(f"[Download] Item Information文件已添加到ZIP: {arcname}")
                except Exception as e:
                    current_app.logger.error(f"[Download] Failed writing Item Information {item_info_path} to ZIP: {e}")
            
            # 添加日志文件
            try:
                zipf.write(log_path, log_filename)
                current_app.logger.info(f"日志文件已添加到ZIP: {log_filename}")
            except Exception as e:
                current_app.logger.error(f"Failed writing log to ZIP: {e}")
        
        # 删除临时日志文件（可选，保留也可以）
        # log_path.unlink()

        return jsonify({
            'success': True,
            'message': f'Successfully downloaded {total_success_count} image(s) from {len(cert_numbers)} certificate(s)' if language == 'en'
                      else f'成功从 {len(cert_numbers)} 个证书下载 {total_success_count} 张图片',
            'image_urls': all_image_urls,
            'cert_info': cert_info,
            'download_url': f'/api/download_file/{zip_filename}',
            'cert_numbers': [downloader._extract_cert_number(cn) for cn in cert_numbers]
        })
    except ValueError as e:
        current_app.logger.error(f"ValueError in download_images: {str(e)}")
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        return jsonify({
            'success': False,
            'message': str(e) if language == 'en' else '无效的证书编号'
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error in download_images: {str(e)}", exc_info=True)
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        error_msg = str(e)
        error_type = type(e).__name__
        
        # 检查是否是连接错误
        is_connection_error = (
            'ConnectionError' in error_type or 
            'Connection' in error_type or
            '10061' in error_msg or 
            'actively refused' in error_msg.lower() or 
            '拒绝' in error_msg or
            '无法连接到' in error_msg
        )
        
        if language == 'zh':
            if is_connection_error:
                error_msg = '无法连接到PSA网站服务器，请检查网络连接或稍后重试'
            elif '无法访问' in error_msg or 'unable to access' in error_msg.lower():
                error_msg = '无法访问PSA网站，请检查网络连接'
            elif 'not found' in error_msg.lower() or '未找到' in error_msg:
                error_msg = '未找到该证书编号的图片'
        else:
            if is_connection_error:
                error_msg = 'Unable to connect to PSA website server, please check your network connection or try again later'
            elif 'unable to access' in error_msg.lower():
                error_msg = 'Unable to access PSA website, please check your network connection'
            elif 'not found' in error_msg.lower():
                error_msg = 'No images found for this certificate number'
        
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500


@api_bp.route('/preview', methods=['POST'])
def preview_images():
    current_app.logger.info("=" * 60)
    current_app.logger.info("[Preview] ========== 收到预览请求 ==========")
    try:
        # 记录请求信息
        current_app.logger.info(f"[Preview] 请求方法: {request.method}")
        current_app.logger.info(f"[Preview] 请求头: {dict(request.headers)}")
        current_app.logger.info(f"[Preview] Content-Type: {request.content_type}")
        
        data = request.get_json()
        current_app.logger.info(f"[Preview] 请求数据: {data}")
        
        if not data:
            current_app.logger.warning("[Preview] 请求数据为空")
            return jsonify({
                'success': False,
                'message': 'Invalid request: JSON data required'
            }), 400

        language = data.get('language', 'en')
        image_size = data.get('image_size', 'large')  # 预览默认使用large尺寸
        cert_numbers = data.get('cert_numbers', [])
        cert_number = data.get('cert_number', '').strip()
        if not cert_numbers and cert_number:
            cert_numbers = [cert_number]
        elif cert_numbers and isinstance(cert_numbers, str):
            cert_numbers = [cn.strip() for cn in cert_numbers.split('+') if cn.strip()]

        current_app.logger.info(f"[Preview] 证书编号列表: {cert_numbers}")
        current_app.logger.info(f"[Preview] 语言: {language}")
        current_app.logger.info(f"[Preview] 图片尺寸: {image_size}")

        if not cert_numbers:
            current_app.logger.warning("[Preview] 未提供证书编号")
            return jsonify({
                'success': False,
                'message': 'Certificate number is required' if language == 'en' else '请输入证书编号'
            }), 400

        downloader = current_app.config['DOWNLOADER']
        all_image_urls = {}
        cert_info = {}

        for cert_num in cert_numbers:
            if not cert_num.strip():
                continue
            current_app.logger.info(f"[Preview] 开始处理证书: {cert_num}")
            try:
                # 使用新的统一模块查找图片（预览模式使用指定的尺寸，默认large）
                image_list, extracted_num, page_title = find_certificate_images(
                    downloader=downloader,
                    cert_number=cert_num,
                    target_size=image_size,  # 使用请求中指定的尺寸
                    logger=current_app.logger,
                    max_images=10  # 预览可以返回更多图片
                )
                
                # 提取URL列表用于返回
                urls = [url for url, _, _ in image_list]
                all_image_urls[extracted_num] = urls
                cert_info[extracted_num] = {'title': page_title, 'original': cert_num}
                
                current_app.logger.info(f"[Preview] 证书 {extracted_num} 处理完成: 找到 {len(urls)} 张图片")
                if urls:
                    for i, url in enumerate(urls, 1):
                        current_app.logger.info(f"[Preview]   {i}. {url}")
                else:
                    current_app.logger.warning(f"[Preview] 证书 {extracted_num} 未找到任何图片")
            except Exception as e:
                current_app.logger.error(f"[Preview] 处理证书 {cert_num} 时出错: {str(e)}", exc_info=True)
                import traceback
                current_app.logger.error(f"[Preview] 完整错误堆栈:\n{traceback.format_exc()}")
                try:
                    extracted_num = downloader._extract_cert_number(cert_num)
                except:
                    extracted_num = cert_num
                all_image_urls[extracted_num] = []
                cert_info[extracted_num] = {'title': f'Error: {str(e)}', 'original': cert_num}

        total_count = sum(len(urls) for urls in all_image_urls.values())
        current_app.logger.info(f"[Preview] 总计找到 {total_count} 张图片（来自 {len(cert_numbers)} 个证书）")
        
        # 如果所有证书都没有找到图片，返回错误（但使用200状态码，因为请求已成功处理）
        if total_count == 0:
            current_app.logger.warning(f"[Preview] ========== 预览失败：所有证书都未找到图片 ==========")
            current_app.logger.warning(f"[Preview] 证书编号: {cert_numbers}")
            current_app.logger.warning(f"[Preview] 图片URL: {all_image_urls}")
            current_app.logger.warning(f"[Preview] 证书信息: {cert_info}")
            current_app.logger.warning(f"[Preview] ==============================================")
            return jsonify({
                'success': False,
                'message': 'No images found for the certificate(s)' if language == 'en' else '未找到该证书编号的图片',
                'image_urls': all_image_urls,
                'cert_info': cert_info,
                'count': 0
            }), 200
        
        current_app.logger.info(f"[Preview] ========== 预览成功 ==========")
        current_app.logger.info(f"[Preview] 返回 {total_count} 张图片")
        current_app.logger.info(f"[Preview] ========================================")
        return jsonify({
            'success': True,
            'image_urls': all_image_urls,
            'cert_info': cert_info,
            'count': total_count
        })
    except ValueError as e:
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        current_app.logger.error(f"[Preview] ValueError: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e) if language == 'en' else '无效的证书编号'
        }), 400
    except Exception as e:
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        current_app.logger.error(f"[Preview] ========== 预览发生未捕获异常 ==========")
        current_app.logger.error(f"[Preview] 错误类型: {type(e).__name__}")
        current_app.logger.error(f"[Preview] 错误消息: {str(e)}", exc_info=True)
        import traceback
        current_app.logger.error(f"[Preview] 完整堆栈跟踪:\n{traceback.format_exc()}")
        current_app.logger.error(f"[Preview] ==============================================")
        error_msg = str(e)
        error_type = type(e).__name__
        
        # 检查是否是连接错误
        is_connection_error = (
            'ConnectionError' in error_type or 
            'Connection' in error_type or
            '10061' in error_msg or 
            'actively refused' in error_msg.lower() or 
            '拒绝' in error_msg or
            '无法连接到' in error_msg
        )
        
        if language == 'zh':
            if is_connection_error:
                error_msg = '无法连接到PSA网站服务器，请检查网络连接或稍后重试'
            elif '无法访问' in error_msg or 'unable to access' in error_msg.lower():
                error_msg = '无法访问PSA网站，请检查网络连接'
            elif 'not found' in error_msg.lower() or '未找到' in error_msg:
                error_msg = '未找到该证书编号的图片'
        else:
            if is_connection_error:
                error_msg = 'Unable to connect to PSA website server, please check your network connection or try again later'
            elif 'unable to access' in error_msg.lower():
                error_msg = 'Unable to access PSA website, please check your network connection'
            elif 'not found' in error_msg.lower():
                error_msg = 'No images found for this certificate number'
        
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500


@api_bp.route('/download_file/<filename>')
def download_file(filename):
    zip_path = current_app.config['DOWNLOAD_DIR'] / filename
    if not zip_path.exists():
        return jsonify({'error': 'File not found'}), 404
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/zip'
    )


@api_bp.route('/health')
def health():
    return jsonify({'status': 'ok'})


