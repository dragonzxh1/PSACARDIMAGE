"""
PSA Card Image Downloader Web Application
Flask-based web interface for downloading PSA card high-resolution images
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import zipfile
import re
from pathlib import Path
from urllib.parse import urlparse
from psa_card_downloader import PSACardImageDownloader
import threading
import time

app = Flask(__name__)
CORS(app)

# 配置日志
import logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
DOWNLOAD_DIR = Path('downloads')
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Global downloader instance (禁用SSL验证以避免证书问题，并支持自动切换域名)
downloader = PSACardImageDownloader(verify_ssl=False)


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/download', methods=['POST'])
def download_images():
    """
    API endpoint for downloading PSA card images
    
    Request body:
    {
        "cert_number": "96098359",
        "language": "en" or "zh"
    }
    
    Returns:
    {
        "success": true/false,
        "message": "status message",
        "image_urls": [...],
        "download_url": "/api/download_file/PSA_96098359.zip" (if success)
    }
    """
    try:
        data = request.get_json()
        cert_number = data.get('cert_number', '').strip()
        language = data.get('language', 'en')
        image_size = data.get('image_size', 'original').strip().lower()  # original, large, medium, small
        
        if not cert_number:
            return jsonify({
                'success': False,
                'message': 'Certificate number is required' if language == 'en' else '请输入证书编号'
            }), 400
        
        # 验证image_size参数
        valid_sizes = ['original', 'large', 'medium', 'small']
        if image_size not in valid_sizes:
            image_size = 'original'  # 默认使用原图
        
        # Get images for download (强制使用原图，不管前端选择什么尺寸)
        image_urls, page_title = downloader.get_high_res_images(cert_number, preview_mode=False, image_size='original')
        
        if not image_urls:
            cert_num = downloader._extract_cert_number(cert_number)
            return jsonify({
                'success': False,
                'message': f'No images found for certificate {cert_num}' if language == 'en' 
                          else f'未找到证书 {cert_num} 的图片'
            }), 404
        
        # Extract certificate number for folder naming
        cert_num = downloader._extract_cert_number(cert_number)
        save_path = DOWNLOAD_DIR / f"PSA_{cert_num}"
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 去重：基于文件名去重，确保每个文件只下载一次
        seen_filenames = set()
        unique_urls = []
        for url in image_urls:
            url_clean = url.rstrip('\\/').strip()
            parsed_url = urlparse(url_clean)
            filename = os.path.basename(parsed_url.path).rstrip('\\/')
            if not filename or '.' not in filename:
                filename = f"unknown_{len(unique_urls)}.jpg"
            
            # 过滤掉不必要的文件
            filename_lower = filename.lower()
            exclude_keywords = [
                'table-image', 'certified', 'logo', 'icon', 'button', 'badge', 
                'avatar', 'spinner', 'loading', 'placeholder',
                'og-meta', 'meta', 'og-image', 'social', 'share'  # 排除meta和社交媒体图片
            ]
            if any(keyword in filename_lower for keyword in exclude_keywords):
                app.logger.info(f"跳过不必要的文件: {filename}")
                continue
            
            # 额外检查：如果URL包含meta路径，也跳过
            url_lower = url.lower()
            if '/meta/' in url_lower or '/social/' in url_lower:
                app.logger.info(f"跳过meta/social图片: {url[:100]}")
                continue
            
            if filename not in seen_filenames:
                seen_filenames.add(filename)
                unique_urls.append(url_clean)
            else:
                app.logger.info(f"跳过重复文件: {filename} (URL: {url_clean[:100]})")
        
        app.logger.info(f"去重后：{len(image_urls)} -> {len(unique_urls)} 个唯一文件")
        
        if not unique_urls:
            return jsonify({
                'success': False,
                'message': 'No unique images found after deduplication' if language == 'en' else '去重后未找到唯一图片'
            }), 404
        
        # Download images
        success_count = 0
        downloaded_files = []
        
        app.logger.info(f"Downloading {len(unique_urls)} image(s) for certificate {cert_num}")
        
        for i, url in enumerate(unique_urls, 1):
            # 清理URL（移除末尾的反斜杠等）
            url = url.rstrip('\\/').strip()
            app.logger.info(f"Downloading image {i}/{len(unique_urls)}: {url}")
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path).rstrip('\\/')
            if not filename or '.' not in filename:
                filename = f"image_{i}.jpg"
            
            try:
                app.logger.info(f"Attempting to download: {url}")
                response = downloader.session.get(url, timeout=30, stream=True, verify=downloader.verify_ssl)
                response.raise_for_status()
                
                file_path = save_path / filename
                
                # 如果文件已存在，跳过（避免重复下载）
                if file_path.exists():
                    app.logger.info(f"文件已存在，跳过: {filename}")
                    downloaded_files.append(file_path)
                    success_count += 1
                    continue
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                downloaded_files.append(file_path)
                success_count += 1
                file_size = file_path.stat().st_size
                app.logger.info(f"Successfully downloaded: {filename} ({file_size} bytes)")
            except Exception as e:
                app.logger.error(f"Failed to download {url}: {str(e)}", exc_info=True)
                continue
        
        if success_count == 0:
            return jsonify({
                'success': False,
                'message': 'Failed to download images' if language == 'en' else '图片下载失败'
            }), 500
        
        # Create zip file
        zip_path = DOWNLOAD_DIR / f"PSA_{cert_num}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in downloaded_files:
                zipf.write(file_path, file_path.name)
        
        return jsonify({
            'success': True,
            'message': f'Successfully downloaded {success_count} image(s)' if language == 'en'
                      else f'成功下载 {success_count} 张图片',
            'image_urls': image_urls,
            'download_url': f'/api/download_file/PSA_{cert_num}.zip',
            'cert_number': cert_num
        })
        
    except ValueError as e:
        app.logger.error(f"ValueError in download_images: {str(e)}")
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        return jsonify({
            'success': False,
            'message': str(e) if language == 'en' else '无效的证书编号'
        }), 400
    except Exception as e:
        app.logger.error(f"Error in download_images: {str(e)}", exc_info=True)
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        error_msg = str(e)
        if language == 'zh':
            if '无法访问' in error_msg or 'unable to access' in error_msg.lower():
                error_msg = '无法访问PSA网站，请检查网络连接'
            elif 'not found' in error_msg.lower() or '未找到' in error_msg:
                error_msg = '未找到该证书编号的图片'
        return jsonify({
            'success': False,
            'message': f'An error occurred: {error_msg}' if language == 'en' else f'发生错误: {error_msg}'
        }), 500


@app.route('/api/preview', methods=['POST'])
def preview_images():
    """
    API endpoint for previewing image URLs without downloading
    
    Request body:
    {
        "cert_number": "96098359",
        "language": "en" or "zh"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request: JSON data required'
            }), 400
        
        cert_number = data.get('cert_number', '').strip()
        language = data.get('language', 'en')
        
        if not cert_number:
            return jsonify({
                'success': False,
                'message': 'Certificate number is required' if language == 'en' else '请输入证书编号'
            }), 400
        
        # Get images for preview (强制使用large缩略图)
        app.logger.info(f"Preview request for certificate: {cert_number}")
        image_urls, page_title = downloader.get_high_res_images(cert_number, preview_mode=True, image_size='large')
        
        return jsonify({
            'success': True,
            'image_urls': image_urls,
            'page_title': page_title,
            'count': len(image_urls)
        })
        
    except ValueError as e:
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        app.logger.error(f"ValueError in preview_images: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e) if language == 'en' else '无效的证书编号'
        }), 400
    except Exception as e:
        language = request.get_json().get('language', 'en') if request.get_json() else 'en'
        app.logger.error(f"Error in preview_images: {str(e)}", exc_info=True)
        error_msg = str(e)
        if language == 'zh':
            if '无法访问' in error_msg or 'unable to access' in error_msg.lower():
                error_msg = '无法访问PSA网站，请检查网络连接'
            elif 'not found' in error_msg.lower() or '未找到' in error_msg:
                error_msg = '未找到该证书编号的图片'
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500


@app.route('/api/download_file/<filename>')
def download_file(filename):
    """Download the zip file"""
    zip_path = DOWNLOAD_DIR / filename
    
    if not zip_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/zip'
    )


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

