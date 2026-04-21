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
            "origins": "*", 

            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # 加载配置
    # 强制覆盖模式，确保 .env 文件中的值始终生效
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        logger.warning("python-dotenv not installed, skipping .env loading")

    # 关键配置日志
    logger.info(f"Active WECHAT_NOTIFY_URL: {os.getenv('WECHAT_NOTIFY_URL')}")

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
    
    # 辅助接口：允许手动触发订单同步 (用于回调失败时的补救)
    @app.route('/api/pay/sync/<tenant_key>', methods=['GET', 'POST'])
    def sync_tenant_orders(tenant_key):
        quota_service = app.config['QUOTA_SERVICE']
        wechat_pay_service = app.config['WECHAT_PAY_SERVICE']
        
        # 获取该租户所有 PENDING 状态的订单
        try:
            import sqlite3
            with sqlite3.connect(quota_service.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT order_id FROM payment_orders WHERE tenant_key = ? AND status = 'PENDING'", (tenant_key,))
                pending_orders = [row[0] for row in cursor.fetchall()]
            
            synced_count = 0
            for order_id in pending_orders:
                result = wechat_pay_service.query_order(order_id)
                if result and result.get('trade_state') == 'SUCCESS':
                    transaction_id = result.get('transaction_id')
                    quota_service.update_payment_status(order_id, 'SUCCESS', transaction_id)
                    synced_count += 1
            
            return {"code": 0, "msg": f"Synced {len(pending_orders)} orders, {synced_count} updated to SUCCESS"}, 200
        except Exception as e:
            return {"code": -1, "msg": str(e)}, 500

    app.register_blueprint(page_bp)

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=True)

