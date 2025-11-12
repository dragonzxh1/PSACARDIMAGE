from flask import Flask
from flask_cors import CORS
from pathlib import Path
import logging
from psa_card_downloader import PSACardImageDownloader
from .routes import api_bp, page_bp


def create_app() -> Flask:
    # Ensure Flask looks for templates in the project-level 'templates' directory
    project_root = Path(__file__).resolve().parent.parent
    templates_dir = project_root / 'templates'
    app = Flask(__name__, template_folder=str(templates_dir))
    CORS(app)

    # Logging - 确保日志输出到控制台
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # 输出到控制台
        ]
    )
    app.logger.setLevel(logging.INFO)
    # 确保Flask的日志也输出到控制台
    app.logger.handlers = [logging.StreamHandler()]
    for handler in app.logger.handlers:
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # Config
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
    # Use absolute path under project root to avoid CWD-related issues
    download_dir = project_root / 'downloads'
    download_dir.mkdir(exist_ok=True)
    app.config['DOWNLOAD_DIR'] = download_dir

    # Shared services
    downloader = PSACardImageDownloader(verify_ssl=False)
    app.config['DOWNLOADER'] = downloader

    # Blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(page_bp)

    return app


