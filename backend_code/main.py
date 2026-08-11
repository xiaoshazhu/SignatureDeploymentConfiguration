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

import threading
# 全局网络流量统计变量（用于进程级网络吞吐计算，对齐 Node.js 估算）
net_lock = threading.Lock()
net_in_bytes = 0
net_out_bytes = 0

def report_error_to_platform(error, context="", tenant_key=""):
    try:
        import urllib.request
        import traceback
        import json
        
        platform_log_url = os.getenv("PLATFORM_LOG_URL") or "http://127.0.0.1:8080/api/v1/plugin/log/report"
        token = os.getenv("API_TOKEN")
        if not token:
            logger.error("API_TOKEN not set, skipping exception report")
            return
        
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__)) if hasattr(error, '__traceback__') else ""
        
        payload = {
            "level": "error",
            "message": f"[{context}] {str(error)}" if context else str(error),
            "stackTrace": tb or str(error),
            "requestPath": context or "Flask Exception Handler",
            "tenantKey": tenant_key
        }
        
        req = urllib.request.Request(
            platform_log_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            },
            method="POST"
        )
        
        def send_req():
            try:
                with urllib.request.urlopen(req, timeout=3) as response:
                    response.read()
            except Exception as ex:
                logger.error(f"Failed to send exception to platform: {ex}")
                
        import threading
        threading.Thread(target=send_req, daemon=True).start()
    except Exception as ex:
        logger.error(f"Failed to prepare error report: {ex}")

def start_websocket_heartbeat():
    import threading
    import time
    import websocket
    import psutil
    import json

    def run():
        time.sleep(2)  # 等待 Flask 启动完毕
        ws_url = os.getenv("PLATFORM_WS_URL")
        if not ws_url:
            logger.warning("[WS Heartbeat] PLATFORM_WS_URL not configured. WebSocket metrics reporting disabled.")
            return

        logger.info(f"[WS Heartbeat] Starting WebSocket heartbeat connection: {ws_url}")
        
        # 初始网卡采样 (仅采样开始时间)
        time_before = time.time()

        while True:
            try:
                ws = websocket.create_connection(ws_url, timeout=5)
                logger.info("[WS Heartbeat] WebSocket connection successfully established.")
                proc = psutil.Process()
                proc.cpu_percent(interval=None)  # 首次调用 warm up
                while True:
                    time.sleep(2)
                    try:
                        raw_cpu = proc.cpu_percent(interval=None)
                        cpu = round(raw_cpu / psutil.cpu_count(), 1)
                    except Exception:
                        cpu = -1.0
                    try:
                        mem = round(proc.memory_percent(), 2)
                    except Exception:
                        mem = -1.0
                    
                    # 1. 估算磁盘使用率
                    try:
                        disk_usage = psutil.disk_usage('/').percent
                    except Exception:
                        disk_usage = -1.0
                    
                    # 2. 估算日志物理大小
                    log_size = -1.0
                    try:
                        log_path = 'app.log'
                        if os.path.exists(log_path):
                            log_size = round(os.path.getsize(log_path) / (1024 * 1024), 3)
                        else:
                            log_size = 0.0
                    except Exception:
                        pass
                    
                    # 3. 计算网络流量速率 (进程级 HTTP 流量)
                    time_after = time.time()
                    dt = time_after - time_before
                    net_in_rate = 0.0
                    net_out_rate = 0.0
                    if dt > 0:
                        global net_in_bytes, net_out_bytes
                        with net_lock:
                            in_rate = (net_in_bytes / 1024.0) / dt
                            out_rate = (net_out_bytes / 1024.0) / dt
                            net_in_bytes = 0
                            net_out_bytes = 0
                        net_in_rate = round(in_rate, 2)
                        net_out_rate = round(out_rate, 2)
                    time_before = time_after
                    
                    # 4. 系统句柄与线程数
                    try:
                        threads_count = proc.num_threads()
                    except Exception:
                        threads_count = -1
                    
                    try:
                        open_fds = proc.num_fds()
                    except AttributeError:
                        try:
                            open_fds = proc.num_handles()
                        except Exception:
                            open_fds = -1
                    except Exception:
                        open_fds = -1
                        
                    try:
                        conn_count = len(proc.net_connections())
                    except AttributeError:
                        try:
                            conn_count = len(proc.connections())
                        except Exception:
                            conn_count = -1
                    except Exception:
                        conn_count = -1
                        
                    try:
                        uptime = int(time.time() - proc.create_time())
                    except Exception:
                        uptime = -1

                    # 增加 Python 递归计算文件夹体积的逻辑
                    def get_dir_size(path_dir):
                        total_size = 0
                        try:
                            for dirpath, dirnames, filenames in os.walk(path_dir):
                                # 排除第三方依赖 venv, .git 和 Python 编译缓存 __pycache__
                                dirnames[:] = [d for d in dirnames if d not in ('venv', '.git', '__pycache__') and not d.endswith('_venv')]
                                for f in filenames:
                                    fp = os.path.join(dirpath, f)
                                    if not os.path.islink(fp):
                                        total_size += os.path.getsize(fp)
                        except Exception:
                            pass
                        return total_size
                    plugin_disk_usage = round(get_dir_size('.') / (1024 * 1024), 2)

                    payload = {
                        "type": "metrics",
                        "cpu_usage": cpu,
                        "memory_usage": mem,
                        "disk_usage": disk_usage,
                        "plugin_disk_usage": plugin_disk_usage,
                        "log_size": log_size,
                        "network_in": net_in_rate,
                        "network_out": net_out_rate,
                        "process_threads": threads_count,
                        "open_handles": open_fds,
                        "connection_count": conn_count,
                        "uptime": uptime,
                        "metadata": {
                            "network_source": "app_http_estimated",
                            "disk_source": "host_root_partition",
                            "collector_version": "1.0.1",
                            "collector_lang": "python"
                        }
                    }
                    ws.send(json.dumps(payload))
            except Exception as e:
                logger.warning(f"[WS Heartbeat] Connection lost or failed to connect: {e}. Reconnecting in 5 seconds...")
                time.sleep(5)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

def create_app():
    app = Flask(__name__)
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.debug = debug_mode
    
    # 注入进程级 HTTP 流量估算统计（对齐 Node.js）
    from flask import request
    
    @app.before_request
    def track_in_traffic():
        global net_in_bytes
        try:
            content_length = request.content_length
            if content_length is None:
                headers_size = sum(len(k) + len(v) for k, v in request.headers.items())
                content_length = len(request.path) + headers_size
            with net_lock:
                net_in_bytes += content_length
        except Exception:
            pass

    @app.after_request
    def track_out_traffic(response):
        global net_out_bytes
        try:
            content_length = response.content_length
            if content_length is None:
                content_length = len(response.get_data())
            with net_lock:
                net_out_bytes += content_length
        except Exception:
            pass
        return response
    
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
    quota_service = QuotaService()
    lark_client = LarkClient(app_id, app_secret, personal_base_token, base_app_token, quota_service=quota_service)
    sign_service = SignService(lark_client, sign_archive_table_id)
    wechat_pay_service = WechatPayService()
    
    # 注入服务到 app config
    app.config['LARK_CLIENT'] = lark_client  
    app.config['SIGN_SERVICE'] = sign_service
    app.config['QUOTA_SERVICE'] = quota_service
    app.config['WECHAT_PAY_SERVICE'] = wechat_pay_service
    app.config['BASE_APP_TOKEN'] = os.getenv("BASE_APP_TOKEN")

    # 注册路由
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # 辅助接口：允许手动触发订单同步 (用于回调失败时的补救)
    @app.route('/api/pay/sync/<tenant_key>', methods=['GET', 'POST'])
    def sync_tenant_orders(tenant_key):
        quota_service = app.config['QUOTA_SERVICE']
        wechat_pay_service = app.config['WECHAT_PAY_SERVICE']
        
        try:
            from datetime import datetime, timedelta
            cutoff_time = datetime.now() - timedelta(hours=2)
            
            # 使用 MySQL _execute_query 检索订单 (替换原 SQLite 直接查询)
            rows = quota_service._execute_query(
                "SELECT order_id FROM payment_orders WHERE tenant_key = %s AND status = 'PENDING' AND created_at > %s", 
                (tenant_key, cutoff_time), fetch_all=True
            )
            pending_orders = [row[0] for row in rows]
            
            synced_count = 0
            if pending_orders:
                logger.info(f"Checking {len(pending_orders)} recent pending orders for {tenant_key}")
                for order_id in pending_orders:
                    result = wechat_pay_service.query_order(order_id)
                    if result and result.get('trade_state') == 'SUCCESS':
                        transaction_id = result.get('transaction_id')
                        quota_service.update_payment_status(order_id, 'SUCCESS', transaction_id)
                        synced_count += 1
            
            return {"code": 0, "msg": f"Synced {len(pending_orders)} recent orders, {synced_count} updated to SUCCESS"}, 200
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return {"code": -1, "msg": str(e)}, 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        logger.error(f"[ErrorHandler] Uncaught exception: {e}", exc_info=True)
        report_error_to_platform(e, "Flask Exception Handler")
        return {"code": 500, "msg": str(e)}, 500

    app.register_blueprint(page_bp)

    # 启动 WebSocket 监控心跳守护线程 (防调试热重载下启动两次)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_websocket_heartbeat()

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 3002))
    debug_flag = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug_flag)
