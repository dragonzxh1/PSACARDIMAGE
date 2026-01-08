from flask import Flask
from flask_cors import CORS
from pathlib import Path
import logging
import os
from psa_card_downloader import PSACardImageDownloader
from toc_card_downloader import TOCCardDownloader
from .routes import api_bp, page_bp


class _UnavailableDownloader:
    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self.logger = logger

    def get_card_info(self, *args, **kwargs):
        self.logger.warning("%s downloader is not configured.", self.name)
        return None


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
    verify_ssl = os.getenv("PSA_VERIFY_SSL", "true").lower() in ("1", "true", "yes", "on")
    psa_downloader = PSACardImageDownloader(verify_ssl=verify_ssl)
    toc_downloader = TOCCardDownloader(output_dir=str(download_dir / "toc_cards"))
    app.config['DOWNLOADER'] = psa_downloader
    app.config['PSA_DOWNLOADER'] = psa_downloader
    app.config['CGC_DOWNLOADER'] = psa_downloader
    app.config['TOC_DOWNLOADER'] = toc_downloader
    app.config['RPA_DOWNLOADER'] = _UnavailableDownloader("RPA", app.logger)

    # Blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(page_bp)

    return app

