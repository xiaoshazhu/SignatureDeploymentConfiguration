import os
import logging
from flask import Flask
from flask_cors import CORS
from services.lark_service import LarkClient
from services.sign_service import SignService
from routes.api_routes import api_bp
from routes.page_routes import page_bp

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    
    # 启用CORS,允许跨域请求
    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://localhost:5173", "https://172.20.20.3:5173", "https://*.feishu.cn"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # 加载配置
    # 尝试加载 .env (如果 python-dotenv 存在)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("python-dotenv not installed, skipping .env loading")

    app_id = os.getenv("APP_ID")
    app_secret = os.getenv("APP_SECRET")
    sign_archive_table_id = os.getenv("SIGN_ARCHIVE_TABLE_ID")
    
    # 简单的配置检查
    if not app_id or not app_secret:
        logger.warning("APP_ID or APP_SECRET not set in environment variables")

    # 初始化服务
    lark_client = LarkClient(app_id, app_secret)
    sign_service = SignService(lark_client, sign_archive_table_id)
    
    # 注入服务到 app config (修复配置名称)
    app.config['LARK_CLIENT'] = lark_client  # 修复:从LarkClient改为LARK_CLIENT
    app.config['SIGN_SERVICE'] = sign_service
    app.config['BASE_APP_TOKEN'] = os.getenv("BASE_APP_TOKEN") # 可选

    # 注册路由
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(page_bp)

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=True)

