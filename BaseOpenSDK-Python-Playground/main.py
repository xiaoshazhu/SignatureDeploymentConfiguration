import os
import logging
from flask import Flask
from flask_cors import CORS
from services.lark_service import LarkClient
from services.sign_service import SignService
from services.quota_service import QuotaService
from services.wechat_pay_service import WechatPayService
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
    personal_base_token = os.getenv("PERSONAL_BASE_TOKEN")
    base_app_token = os.getenv("BASE_APP_TOKEN")
    sign_archive_table_id = os.getenv("SIGN_ARCHIVE_TABLE_ID")
    
    # 简单的配置检查
    if not personal_base_token:
        logger.warning("PERSONAL_BASE_TOKEN not set in environment variables")
    if not app_id or not app_secret:
        logger.warning("APP_ID or APP_SECRET not set in environment variables (needed for some non-bitable APIs if any)")

    # 初始化服务
    lark_client = LarkClient(app_id, app_secret, personal_base_token, base_app_token)
    sign_service = SignService(lark_client, sign_archive_table_id)
    quota_service = QuotaService(os.path.join(os.path.dirname(__file__), 'quota.db'))
    wechat_pay_service = WechatPayService()
    
    # 注入服务到 app config (修复配置名称)
    app.config['LARK_CLIENT'] = lark_client  # 修复:从LarkClient改为LARK_CLIENT
    app.config['SIGN_SERVICE'] = sign_service
    app.config['QUOTA_SERVICE'] = quota_service
    app.config['WECHAT_PAY_SERVICE'] = wechat_pay_service
    app.config['BASE_APP_TOKEN'] = os.getenv("BASE_APP_TOKEN") # 可选

    # 注册路由
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(page_bp)

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=True)

