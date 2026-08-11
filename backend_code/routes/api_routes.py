from flask import Blueprint, request, jsonify, current_app
import logging
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime
from uuid import uuid4
from utils.crypto_utils import encrypt_url_params, decrypt_url_params
import psutil
import requests
import os

# 初始化进程级性能采集对象
_proc = psutil.Process()
_proc.cpu_percent(interval=None)  # 首次调用 warm up

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# 辅助函数:脱敏app_token
def mask_token(token):
    """脱敏token,只显示前8个字符"""
    if not token:
        return "None"
    return token[:8] + "..." if len(token) > 8 else token

@api_bp.route('/config/set-token', methods=['POST'])
def set_personal_base_token():
    """动态设置个人授权码 (Personal Base Token)"""
    data = request.json
    token = data.get('personal_base_token')
    tenant_key = data.get('tenant_key')
    
    if not token:
        return jsonify({"code": 400, "msg": "授权码不能为空"}), 400
    if not tenant_key:
        return jsonify({"code": 400, "msg": "缺少租户标识，无法保存授权码"}), 400
    
    quota_service = current_app.config['QUOTA_SERVICE']
    success = quota_service.set_personal_base_token(tenant_key, token)
    
    if success:
        return jsonify({"code": 0, "msg": "授权码设置成功并已持久化"})
    else:
        return jsonify({"code": 500, "msg": "保存授权码失败"}), 500

@api_bp.route('/config/check', methods=['GET'])
def check_config():
    """检查后台配置状态"""
    tenant_key = request.args.get('tenant_key')
    token_set = False
    
    quota_service = current_app.config['QUOTA_SERVICE']
    if tenant_key:
        token = quota_service.get_personal_base_token(tenant_key)
        token_set = bool(token)
    else:
        # 兼容未传 tenant_key 时的旧检查逻辑
        lark_client = current_app.config['LARK_CLIENT']
        token_set = bool(lark_client.personal_base_token)
        
    wechat_pay_service = current_app.config['WECHAT_PAY_SERVICE']
    return jsonify({
        "code": 0,
        "data": {
            "token_set": token_set,
            "notify_url": wechat_pay_service.notify_url
        }
    })

@api_bp.route('/quota/status', methods=['GET'])
def get_quota_status():
    """获取租户配额状态"""
    tenant_key = request.args.get('tenant_key')
    app_token = request.args.get('app_token')
    if not tenant_key:
        return jsonify({"code": 401, "msg": "未识别到租户标识"}), 401
        
    quota_service = current_app.config['QUOTA_SERVICE']
    
    # 动态记录文档与租户映射
    if app_token:
        quota_service.bind_app_token_to_tenant(app_token, tenant_key)
        
    info = quota_service.get_quota_info(tenant_key)
    
    if info:
        return jsonify({"code": 0, "data": info})
    else:
        return jsonify({"code": 500, "msg": "获取额度信息失败"}), 500

def test_route_only(f):
    import os
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if os.getenv("APP_ENV") != "development":
            return jsonify({"code": 403, "msg": "该测试路由已被禁用（仅在开发环境 development 下开启）"}), 403
        return f(*args, **kwargs)
    return decorated

@api_bp.route('/quota/recharge', methods=['POST'])
@test_route_only
def recharge_quota():
    """充值配额(模拟)"""
    data = request.json
    tenant_key = data.get('tenant_key')
    package_name = data.get('package_name') # 如 "500次套餐"
    added_quota = data.get('added_quota')
    amount = data.get('amount')
    
    if not tenant_key or not added_quota:
        return jsonify({"code": 400, "msg": "参数缺失"}), 400
        
    quota_service = current_app.config['QUOTA_SERVICE']
    success = quota_service.recharge_quota(tenant_key, package_name, added_quota, amount)
    
    if success:
        return jsonify({"code": 0, "msg": "充值成功"})
    else:
        return jsonify({"code": 500, "msg": "充值失败"}), 500

@api_bp.route('/subscription/enterprise-status', methods=['GET'])
def get_enterprise_status():
    """代理向平台端查询当前租户是否登记企业全称"""
    tenant_key = request.args.get('tenant_key')
    if not tenant_key:
        return jsonify({"code": 400, "msg": "缺少 tenant_key 参数"}), 400

    platform_url = os.getenv("PLATFORM_API_URL", "http://127.0.0.1:8080")
    api_token = os.getenv("API_TOKEN")
    if not api_token:
        return jsonify({"code": 500, "msg": "Configuration error: API_TOKEN is not configured"}), 500

    try:
        url = f"{platform_url}/api/plugin/enterprise/status?tenant_key={tenant_key}"
        headers = {"Authorization": f"Bearer {api_token}"}
        res = requests.get(url, headers=headers, timeout=5)
        # 兼容平台端 Go 后端返回的 JSON
        return jsonify(res.json()), res.status_code
    except Exception as e:
        logger.error(f"Failed to query platform enterprise status: {e}")
        return jsonify({"code": 500, "msg": f"平台端接口连接失败: {str(e)}"}), 500

@api_bp.route('/subscription/register-enterprise', methods=['POST'])
def register_enterprise():
    """代理向平台端登记企业名称"""
    data = request.json or {}
    tenant_key = data.get('tenantKey')
    enterprise_name = data.get('enterpriseName')

    if not tenant_key or not enterprise_name:
        return jsonify({"code": 400, "msg": "参数缺失，tenantKey 和 enterpriseName 必填"}), 400

    platform_url = os.getenv("PLATFORM_API_URL", "http://127.0.0.1:8080")
    api_token = os.getenv("API_TOKEN")
    if not api_token:
        return jsonify({"code": 500, "msg": "Configuration error: API_TOKEN is not configured"}), 500

    try:
        url = f"{platform_url}/api/plugin/enterprise/register"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        res = requests.post(url, json=data, headers=headers, timeout=5)
        return jsonify(res.json()), res.status_code
    except Exception as e:
        logger.error(f"Failed to register enterprise name on platform: {e}")
        return jsonify({"code": 500, "msg": f"平台端接口连接失败: {str(e)}"}), 500

@api_bp.route('/subscription/redeem-coupon', methods=['POST'])
def redeem_coupon():
    """
    功能描述：代理向平台端发送兑换码核销请求，马某。
    @param (HTTP Request Body): tenantKey - 租户 Key; couponCode - 兑换码
    @return: json 平台端返回 of 核销响应与状态码
    """
    data = request.json or {}
    tenant_key = data.get('tenantKey')
    coupon_code = data.get('couponCode')

    if not tenant_key or not coupon_code:
        return jsonify({"code": 400, "msg": "参数缺失，tenantKey 和 couponCode 必填"}), 400

    platform_url = os.getenv("PLATFORM_API_URL", "http://127.0.0.1:8080")
    api_token = os.getenv("API_TOKEN")
    if not api_token:
        return jsonify({"code": 500, "msg": "Configuration error: API_TOKEN is not configured"}), 500

    try:
        url = f"{platform_url}/api/plugin/coupon/redeem"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "coupon_code": coupon_code,
            "tenant_key": tenant_key,
            "plugin_id": "plg_signature"
        }
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        return jsonify(res.json()), res.status_code
    except Exception as e:
        logger.error(f"Failed to redeem coupon on platform: {e}")
        return jsonify({"code": 500, "msg": f"平台端接口连接失败: {str(e)}"}), 500

@api_bp.route('/quota/claim-trial', methods=['POST'])
def claim_trial_quota():
    """手动领取 30 次免费试用额度"""
    data = request.json or {}
    tenant_key = data.get('tenant_key')
    if not tenant_key:
        return jsonify({"code": 400, "msg": "缺少 tenant_key 参数"}), 400

    quota_service = current_app.config['QUOTA_SERVICE']
    try:
        quota_service.claim_free_trial(tenant_key)
        return jsonify({"code": 0, "msg": "领用 30 次免费试用成功"})
    except ValueError as val_err:
        return jsonify({"code": 400, "msg": str(val_err)}), 400
    except Exception as e:
        return jsonify({"code": 500, "msg": f"系统内部异常: {str(e)}"}), 500

@api_bp.route('/quota/test/set-low', methods=['POST'])
@test_route_only
def set_test_low_quota():
    """测试用: 强制将余额设为3次"""
    data = request.json
    tenant_key = data.get('tenant_key')
    if not tenant_key:
        return jsonify({"code": 401, "msg": "缺少租户标识"}), 401
        
    quota_service = current_app.config['QUOTA_SERVICE']
    # 强制修改: 总额度改为 (已用 + 3), 这样剩余就是 3
    info = quota_service.get_quota_info(tenant_key)
    if not info:
         return jsonify({"code": 500, "msg": "租户未初始化"}), 500
         
    new_total = info['used'] + 3
    now = datetime.now().isoformat()
    try:
        with quota_service._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
               "UPDATE tenant_quota SET total_quota = %s, expire_time = NULL, billing_type = 'quota', updated_at = %s WHERE tenant_key = %s",
               (new_total, now, tenant_key)
            )
            conn.commit()
        return jsonify({"code": 0, "msg": "已设为3次余额"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/quota/test/add-subscription', methods=['POST'])
@test_route_only
def add_test_subscription():
    """测试用: 直接赠送1年订阅"""
    data = request.json
    tenant_key = data.get('tenant_key')
    if not tenant_key:
        return jsonify({"code": 401, "msg": "缺少租户标识"}), 401
        
    quota_service = current_app.config['QUOTA_SERVICE']
    success = quota_service.recharge_quota(tenant_key, "测试订阅赠送", 0, 0, package_id='plan_year_1')
    
    if success:
        return jsonify({"code": 0, "msg": "成功赠送1年订阅"})
    else:
        return jsonify({"code": 500, "msg": "操作失败"}), 500

@api_bp.route('/quota/test/add-large', methods=['POST'])
@test_route_only
def add_test_large_quota():
    """测试用: 直接增加 100000 额度"""
    data = request.json
    tenant_key = data.get('tenant_key')
    if not tenant_key:
        return jsonify({"code": 401, "msg": "缺少租户标识"}), 401
        
    quota_service = current_app.config['QUOTA_SERVICE']
    success = quota_service.recharge_quota(tenant_key, "测试大额补偿", 100000, 0)
    
    if success:
        return jsonify({"code": 0, "msg": "成功增加100000额度"})
    else:
        return jsonify({"code": 500, "msg": "操作失败"}), 500

@api_bp.route('/quota/test/cancel-subscription', methods=['POST'])
@test_route_only
def cancel_test_subscription():
    """测试用: 取消订阅(将过期时间设为NULL)"""
    data = request.json
    tenant_key = data.get('tenant_key')
    if not tenant_key:
        return jsonify({"code": 401, "msg": "缺少租户标识"}), 401
        
    quota_service = current_app.config['QUOTA_SERVICE']
    now = datetime.now().isoformat()
    try:
        with quota_service._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tenant_quota SET expire_time = NULL, billing_type = 'quota', updated_at = %s WHERE tenant_key = %s",
                (now, tenant_key)
            )
            conn.commit()
        return jsonify({"code": 0, "msg": "订阅已取消"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500


@api_bp.route('/sign/info', methods=['GET'])
def get_sign_info():
    try:
        # 优先尝试解密参数(新版加密链接)
        encrypted_params = request.args.get('p')
        
        if encrypted_params:
            # 使用加密参数
            try:
               params = decrypt_url_params(encrypted_params)
               table_id = params.get('table_id')
               record_id = params.get('record_id')
               user_id = params.get('user_id')
               app_token = params.get('app_token')
               url_mode = params.get('mode')
               url_count = params.get('count')
               logger.info(f"使用加密参数 - table_id: {table_id}, record_id: {record_id}")
            except ValueError as e:
               logger.error(f"参数解密失败: {e}")
               return jsonify({"code": 400, "msg": "无效的链接参数或参数已被篡改"}), 400
        else:
            # 向后兼容:支持明文参数(旧版链接)
            logger.info(f"使用明文参数(向后兼容) - 完整参数: {dict(request.args)}")
            table_id = request.args.get('table_id')
            record_id = request.args.get('record_id')
            user_id = request.args.get('user_id')
            app_token = request.args.get('app_token')
            url_mode = request.args.get('mode')
            url_count = request.args.get('count')
        
        if not table_id or not record_id:
            logger.warning(f"参数缺失 - table_id: {table_id}, record_id: {record_id}")
            return jsonify({"code": 400, "msg": "缺少必需参数"}), 400

        # 从 app config 获取 service
        sign_service = current_app.config['SIGN_SERVICE']
        
        # 尝试从请求参数或配置获取 app_token
        if not app_token:
            app_token = current_app.config.get('BASE_APP_TOKEN')
        
        if not app_token:
            logger.error("app_token 缺失 - 请求参数和配置中都没有找到")
            return jsonify({"code": 400, "msg": "Missing app_token - 请在链接中包含 app_token 参数或在后端 .env 配置 BASE_APP_TOKEN"}), 400

        # 需求8: 验证URL参数配置
        sign_config = None
        if url_mode or url_count:
            sign_config = validate_sign_params(url_mode, url_count)
            logger.info(f"使用URL参数配置 - mode: {sign_config['mode']}, count: {sign_config['count']}")

        data = sign_service.get_sign_info(app_token, table_id, record_id, user_id, sign_config)
        
        logger.info(f"成功获取签字信息 - record_id: {record_id}")
        return jsonify({
            "code": 0,
            "data": data
        })
    except ValueError as e:
        logger.error(f"参数验证失败: {str(e)}")
        return jsonify({"code": 400, "msg": str(e)}), 400
    except Exception as e:
        logger.error(f"获取签字信息失败 - 错误类型: {type(e).__name__}, 错误信息: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500

def validate_sign_params(mode, count):
    """验证签字参数
    
    需求8: URL参数白名单验证
    """
    # 签字模式白名单
    VALID_MODES = ['或签', '会签']
    
    if mode and mode not in VALID_MODES:
        raise ValueError(f"无效的签字模式: {mode},只允许'或签'或'会签'")
    
    # 签字人数验证
    if count:
        try:
            count_int = int(count)
            if count_int < 1 or count_int > 10:
               raise ValueError(f"无效的签字人数: {count},范围必须在1-10之间")
        except (ValueError, TypeError):
            raise ValueError(f"无效的签字人数格式: {count}")
    
    return {
        "mode": mode or '或签',
        "count": int(count) if count else 3
    }

def generate_sign_link_for_record(lark_client, app_token, table_id, record_id, frontend_host, sign_mode='或签', sign_count=3, enable_qrcode=True, lang=None, field_names=None, write_to_bitable=True):
    """为单条记录生成签字链接(复用批量生成逻辑)
    
    Args:
        lark_client: LarkClient 实例
        app_token: 应用 token
        table_id: 表格 ID
        record_id: 记录 ID
        frontend_host: 前端主机地址
        sign_mode: 签字模式(或签/会签)
        sign_count: 签字人数
        enable_qrcode: 是否生成二维码
        field_names: 自定义字段名称字典
        write_to_bitable: 是否直接写入多维表格(批量处理时可设为False,最后统一步次写入)
        
    Returns:
        dict: 包含 sign_url、qr_token 以及 update_fields 的字典
        
    Raises:
        Exception: 生成失败时抛出异常
    """
    # 生成唯一ID
    unique_id = str(int(time.time() * 1000)) + str(random.randint(100000, 999999))
    
    # 构建签字链接 - 使用加密参数
    params = {
        'app_token': app_token,
        'table_id': table_id,
        'record_id': record_id,
        'uid': unique_id,
        'mode': sign_mode,
        'count': str(sign_count)
    }
    
    # 加密参数
    encrypted_params = encrypt_url_params(params)
    sign_url = f"{frontend_host}/sign?p={encrypted_params}"
    
    # 需求: 追加语言标识, 确保签字页能识别当前展示语言
    if lang:
        sign_url += f"&lang={lang}"
    
    # 生成二维码
    qr_token = None
    if enable_qrcode:
        # 需求整改: 如果开启了二维码但生成失败，必须抛出异常以便触发重试机制，不能跳过
        try:
            qr_token = lark_client.generate_qrcode(sign_url, app_token)
            logger.info(f"二维码生成成功 - record_id: {record_id}")
        except Exception as e:
            logger.error(f"生成二维码失败 (将触发整行重试) - record_id: {record_id}, 错误: {e}")
            raise Exception(f"二维码生成失败: {str(e)}")
    else:
        logger.info(f"跳过二维码生成 - record_id: {record_id}")
    
    # 需求: 从参数获取字段名称,否则使用默认值
    if not field_names:
        field_names = {
            "signLink": "签字确认",
            "status": "签字状态",
            "qrcode": "签字二维码"
        }
    
    sign_link_field_name = field_names.get("signLink", "签字确认")
    status_field_name = field_names.get("status", "签字状态")
    qrcode_field_name = field_names.get("qrcode", "签字二维码")
    
    # 使用字段名称更新记录(根据飞书官方文档)
    update_fields = {}
    
    # 签字入口(超链接字段)
    update_fields[sign_link_field_name] = {
        "text": "请点击签字",
        "link": sign_url
    }
    
    # 状态(单选字段)
    update_fields[status_field_name] = "未签字"
    
    # 签字二维码(附件字段)
    if qr_token:
        update_fields[qrcode_field_name] = [{"file_token": qr_token}]
    
    if write_to_bitable:
        logger.info(f"直接写入记录 {record_id}")
        lark_client.update_bitable_record(app_token, table_id, record_id, update_fields)
    
    return {
        "sign_url": sign_url,
        "qr_token": qr_token,
        "update_fields": update_fields
    }

@api_bp.route('/sign/submit', methods=['POST'])
def submit_sign():
    try:
        data = request.json
        
        # 检查是否有加密参数
        encrypted_params = data.get('encrypted_params')
        
        if encrypted_params:
            # 新版加密参数:解密获取参数
            try:
               params = decrypt_url_params(encrypted_params)
               table_id = params.get('table_id')
               record_id = params.get('record_id')
               app_token = params.get('app_token')
               # 将解密后的参数合并到data中
               data['table_id'] = table_id
               data['record_id'] = record_id
               data['app_token'] = app_token
               data['sign_mode'] = params.get('mode')
               data['sign_count'] = params.get('count')
               logger.info(f"使用加密参数提交签名 - table_id: {table_id}, record_id: {record_id}")
            except ValueError as e:
               logger.error(f"签名提交参数解密失败: {e}")
               return jsonify({"code": 400, "msg": "无效的链接参数或参数已被篡改"}), 400
        else:
            # 旧版明文参数:向后兼容
            table_id = data.get('table_id')
            record_id = data.get('record_id')
            app_token = data.get('app_token') or current_app.config.get('BASE_APP_TOKEN')
            logger.info(f"使用明文参数提交签名(向后兼容) - table_id: {table_id}, record_id: {record_id}")
        
        if not table_id or not record_id or not app_token:
            return jsonify({"code": 400, "msg": "缺少必需参数"}), 400

        sign_service = current_app.config['SIGN_SERVICE']
        result = sign_service.submit_sign(app_token, table_id, record_id, data)
        
        return jsonify({
            "code": 0,
            "msg": "签字成功",
            "data": result
        })
    except Exception as e:
        logger.error(f"Error in submit_sign: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/qrcode/generate', methods=['POST'])
def generate_qrcode():
    """生成二维码并直接写入到多维表格"""
    try:
        data = request.json
        url = data.get('url')
        app_token = data.get('app_token')
        table_id = data.get('table_id')
        record_id = data.get('record_id')
        
        if not url or not app_token or not table_id or not record_id:
            return jsonify({"code": 400, "msg": "Missing required parameters"}), 400
        
        logger.info(f"生成二维码 - URL: {url[:50]}..., app_token: {app_token[:20]}...")
        
        # 从 app config 获取 lark_client 和 quota_service
        lark_client = current_app.config['LARK_CLIENT']
        quota_service = current_app.config['QUOTA_SERVICE']
        
        # 获取租户标识
        tenant_key = data.get('tenant_key')
        if not tenant_key:
            return jsonify({"code": 401, "msg": "缺少租户标识"}), 401

        # 动态记录文档与租户映射关系
        quota_service.bind_app_token_to_tenant(app_token, tenant_key)

        # 额度校验
        if not quota_service.check_quota(tenant_key, 1):
            return jsonify({"code": 403, "msg": "套餐余额不足,请及时充值"}), 403
            
        # 生成二维码并上传
        file_token = lark_client.generate_qrcode(url, app_token)
        
        logger.info(f"二维码生成成功 - file_token: {file_token}")
        
        # 直接写入到多维表格的签字二维码列 - 使用字段名称(根据飞书官方文档)
        try:
            update_fields = {
               "签字二维码": [{"file_token": file_token}]
            }
            lark_client.update_bitable_record(app_token, table_id, record_id, update_fields)
            logger.info(f"二维码已写入多维表格 - record_id: {record_id}")
            
            # 操作成功后扣除额度
            quota_service.consume_quota(tenant_key, 1)
        except Exception as e:
            logger.warning(f"写入二维码到多维表格失败: {e}")
            # 即使写入失败,也返回成功,因为二维码已生成
        
        return jsonify({
            "code": 0,
            "msg": "二维码生成并写入成功",
            "data": {
               "file_token": file_token,
               "url": url,
               "written": True
            }
        })
    except Exception as e:
        logger.error(f"生成二维码失败: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/batch/generate-single-link', methods=['POST'])
def generate_single_link():
    """生成单行签字链接
    
    需求8: 单行操作,复用批量生成逻辑
    """
    try:
        data = request.json
        app_token = data.get('app_token')
        table_id = data.get('table_id')
        record_id = data.get('record_id')
        tenant_key = data.get('tenant_key')
        frontend_host = data.get('frontend_host')
        sign_mode = data.get('sign_mode', '或签')
        sign_count = data.get('sign_count', 3)
        enable_qrcode = data.get('enable_qrcode', True) # 需求: 获取二维码开关状态
        lang = data.get('lang') # 需求: 获取语言标识
        field_names = data.get('field_names') # 需求: 获取自定义字段名称
        
        logger.info(f"收到单行生成请求 - table_id: {table_id}, record_id: {record_id}, tenant_key: {tenant_key}")
        logger.info(f"参数详情 - app_token: {mask_token(app_token)}, frontend_host: {frontend_host}")
        
        if not all([app_token, table_id, record_id, frontend_host, tenant_key]):
            missing = []
            if not app_token: missing.append('app_token')
            if not table_id: missing.append('table_id')
            if not record_id: missing.append('record_id')
            if not frontend_host: missing.append('frontend_host')
            if not tenant_key: missing.append('tenant_key')
            logger.error(f"缺少必需参数: {', '.join(missing)}")
            return jsonify({"code": 401, "msg": f"缺少参数或租户标识: {', '.join(missing)}"}), 401
            
        # 额度校验
        quota_service = current_app.config['QUOTA_SERVICE']
        
        # 动态记录文档与租户映射关系
        quota_service.bind_app_token_to_tenant(app_token, tenant_key)
        
        if not quota_service.check_quota(tenant_key, 1):
            return jsonify({"code": 403, "msg": "套餐余额不足,请及时充值"}), 403
        
        # 验证签字参数
        sign_config = validate_sign_params(sign_mode, str(sign_count))
        
        # 获取服务
        lark_client = current_app.config['LARK_CLIENT']
        
        # 复用批量生成的核心逻辑
        result = generate_sign_link_for_record(
            lark_client=lark_client,
            app_token=app_token,
            table_id=table_id,
            record_id=record_id,
            frontend_host=frontend_host,
            sign_mode=sign_config['mode'],
            sign_count=sign_config['count'],
            enable_qrcode=enable_qrcode,
            lang=lang,
            field_names=field_names
        )
        
        logger.info(f"单行链接生成成功 - record_id: {record_id}")
        
        # 扣除额度
        quota_service.consume_quota(tenant_key, 1)

        return jsonify({
            "code": 0,
            "msg": "生成成功",
            "data": {
               "sign_url": result.get('sign_url'),
               "qr_token": result.get('qr_token'),
               "sign_config": sign_config
            }
        })
        
    except ValueError as e:
        logger.error(f"参数验证失败: {str(e)}")
        return jsonify({"code": 400, "msg": str(e)}), 400
    except Exception as e:
        logger.error(f"生成单行链接失败: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/batch/generate-links', methods=['POST'])
def batch_generate_links():
    """批量生成签字链接并写入多维表格"""
    try:
        data = request.json
        app_token = data.get('app_token')
        table_id = data.get('table_id')
        tenant_key = data.get('tenant_key')
        frontend_host = data.get('frontend_host')
        lang = data.get('lang') # 需求: 获取语言设置
        
        # 需求8: 获取批量配置参数
        sign_mode = data.get('sign_mode', '或签')
        sign_count = data.get('sign_count', 3)
        enable_qrcode = data.get('enable_qrcode', True) # 需求: 获取二维码开关状态
        field_names = data.get('field_names') # 需求: 获取自定义字段名称
        
        if not all([app_token, table_id, frontend_host, tenant_key]):
            return jsonify({"code": 401, "msg": "缺少必需参数或租户标识"}), 401
            
        # 额度校验 - 只要剩余额度大于 0 即可（因为可能有很多记录因已生成而被跳过）
        quota_service = current_app.config['QUOTA_SERVICE']
        
        # 动态记录文档与租户映射关系
        quota_service.bind_app_token_to_tenant(app_token, tenant_key)
        
        quota_info = quota_service.get_quota_info(tenant_key)
        remaining_quota = quota_info.get('remaining', 0)
        if remaining_quota <= 0:
            return jsonify({"code": 403, "msg": "套餐余额不足,请及时充值"}), 403
        
        logger.info(f"批量生成链接 - app_token: {mask_token(app_token)}, table_id: {table_id}, mode: {sign_mode}, count: {sign_count}, enable_qrcode: {enable_qrcode}")
        
        # 验证参数
        try:
            sign_config = validate_sign_params(sign_mode, str(sign_count))
            sign_mode = sign_config['mode']
            sign_count = sign_config['count']
        except ValueError as e:
            return jsonify({"code": 400, "msg": str(e)}), 400
        
        # 从 app config 获取 lark_client
        lark_client = current_app.config['LARK_CLIENT']
        
        # 1. 获取记录并填充详情以用于排重过滤
        specified_record_ids = data.get('record_ids', [])
        
        # 批量处理每条记录 - 使用并发优化
        import os
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if specified_record_ids:
            logger.info(f"快速模式：获取指定的 {len(specified_record_ids)} 条记录详情以进行排重过滤...")
            records = []
            def fetch_detail(rid):
                try:
                    return lark_client.get_bitable_record(app_token, table_id, rid)
                except Exception as e:
                    logger.error(f"获取记录详情失败 - record_id: {rid}, 错误: {e}")
                    return {"record_id": rid, "fields": {}}
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(fetch_detail, rid) for rid in specified_record_ids]
                for future in as_completed(futures):
                    res = future.result()
                    if res:
                        records.append(res)
        else:
            # 默认获取所有记录
            records = lark_client.get_records(app_token, table_id)
            
        total = len(records)
        logger.info(f"待过滤记录总数: {total}")
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        # 需求: 从参数获取字段名称,否则使用默认值
        if not field_names:
            field_names = {
               "signLink": "签字确认",
               "status": "签字状态",
               "qrcode": "签字二维码"
            }
        
        # 检查表格是否存在二维码列
        field_map = lark_client.get_bitable_fields(app_token, table_id)
        
        # 过滤排重逻辑：跳过已有链接的记录，避免覆盖
        sign_link_field_name = field_names.get("signLink", "签字确认")
        records_to_process = []
        for r in records:
            fields = r.get("fields") or {}
            existing_link = fields.get(sign_link_field_name)
            
            # 判定链接是否已存在
            is_empty = True
            if existing_link:
                if isinstance(existing_link, dict) and existing_link.get('link'):
                    is_empty = False
                elif isinstance(existing_link, list) and len(existing_link) > 0:
                    is_empty = False
                elif isinstance(existing_link, str) and existing_link.strip():
                    is_empty = False
            
            if is_empty:
                records_to_process.append(r)
            else:
                skip_count += 1
                logger.info(f"记录 {r.get('record_id')} 已存在签字链接，跳过生成")
        
        logger.info(f"排重完成 - 需处理记录数: {len(records_to_process)}, 跳过已存在: {skip_count}")
        
        # 额度限制校验: 如果待处理数超过剩余额度,则截断
        quota_skip_count = 0
        
        if len(records_to_process) > remaining_quota:
            quota_skip_count = len(records_to_process) - remaining_quota
            logger.warning(f"配额不足: 待处理 {len(records_to_process)} 条, 剩余配额 {remaining_quota} 条。将仅处理前 {remaining_quota} 条。")
            records_to_process = records_to_process[:remaining_quota]
        else:
            logger.info(f"配额检查通过: 待处理 {len(records_to_process)} 条, 剩余配额 {remaining_quota} 条")
        
        # 定义线程安全的处理函数
        def process_single_record(record):
            """处理单条记录的线程安全函数"""
            record_id = record.get("record_id")
            try:
               # 使用封装的函数生成链接, 但不立即写入多维表格 (极速模式: 延迟写入)
               result = generate_sign_link_for_record(
                   lark_client=lark_client,
                   app_token=app_token,
                   table_id=table_id,
                   record_id=record_id,
                   frontend_host=frontend_host,
                   sign_mode=sign_mode,
                   sign_count=sign_count,
                   enable_qrcode=enable_qrcode,
                   lang=lang,
                   field_names=field_names,
                   write_to_bitable=False # 延迟写入，由主循环统一执行 Batch Update
               )
               return ('success', record_id, result.get('update_fields'))
            except Exception as e:
               logger.error(f"处理记录失败 - record_id: {record_id}, 错误: {e}")
               return ('error', record_id, str(e))
        
        # 使用线程池并发处理 (极致稳定性模式: 5并发)
        max_workers = min(5, len(records_to_process)) if len(records_to_process) > 0 else 1
        logger.info(f"使用 {max_workers} 个线程并发处理 (长效稳定模式)")
        
        if len(records_to_process) > 0:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
               # 1. 提交所有任务并保持顺序
               futures = [
                   executor.submit(process_single_record, record) 
                   for record in records_to_process
               ]
               
               # 2. 按照提交顺序收集结果 (解决"随机添加"的问题)
               completed = 0
               failed_records = [] 
               batch_updates = []  
               
               for i, future in enumerate(futures):
                   record = records_to_process[i]
                   record_id = record.get("record_id")
                   completed += 1
                   
                   try:
                       result = future.result()
                       if result[0] == 'success':
                           # 严格保持原始顺序放入批量更新列表
                           batch_updates.append({"record_id": record_id, "fields": result[2]})
                       else:
                           error_count += 1
                           failed_records.append(record)
                           logger.error(f"记录处理失败 (将加入重试队列): {record_id}, 错误: {result[2]}")
                   except Exception as e:
                       error_count += 1
                       failed_records.append(record)
                       logger.error(f"任务执行异常 (将加入重试队列): {record_id}, 错误: {e}")
                   
                   if completed % 10 == 0 or completed == len(records_to_process):
                       logger.info(f"处理进度: {completed}/{len(records_to_process)}")

               # === 执行批量写入并计费 ===
               if batch_updates:
                   try:
                       logger.info(f"执行批量写入: {len(batch_updates)} 条记录...")
                       lark_client.batch_update_records(app_token, table_id, batch_updates)
                       success_count += len(batch_updates)
                       quota_service.consume_quota(tenant_key, len(batch_updates))
                       logger.info("批量写入成功")
                   except Exception as e:
                       logger.error(f"批量写入失败: {e}")
                       # 批量写入失败的记录进入重试流程
                       failed_records.extend([{"record_id": u["record_id"]} for u in batch_updates])
                       error_count += len(batch_updates)
            
            # === 强力重试逻辑 (同样使用 Batch Update) ===
            attempt = 1
            while failed_records and attempt <= 3:
               logger.info(f"开始第 {attempt} 轮自动重试，剩余 {len(failed_records)} 条失败记录...")
               import time
               time.sleep(attempt * 2) # 每一轮重试增加等待时间
               
               still_failed = []
               retry_batch_updates = []
               
               for record in failed_records:
                   record_id = record.get("record_id")
                   try:
                       time.sleep(0.5) 
                       res = generate_sign_link_for_record(
                           lark_client=lark_client, app_token=app_token, table_id=table_id,
                           record_id=record_id, frontend_host=frontend_host,
                           sign_mode=sign_mode, sign_count=sign_count,
                           enable_qrcode=enable_qrcode, lang=lang, field_names=field_names,
                           write_to_bitable=False # 延迟写入
                       )
                       retry_batch_updates.append({"record_id": record_id, "fields": res.get('update_fields')})
                   except Exception as e:
                       still_failed.append(record)
               
               if retry_batch_updates:
                   try:
                       lark_client.batch_update_records(app_token, table_id, retry_batch_updates)
                       success_count += len(retry_batch_updates)
                       error_count -= len(retry_batch_updates)
                       quota_service.consume_quota(tenant_key, len(retry_batch_updates))
                       logger.info(f"重试批次写入成功: {len(retry_batch_updates)} 条")
                   except Exception as e:
                       logger.error(f"重试批次写入失败: {e}")
                       still_failed.extend([{"record_id": u["record_id"]} for u in retry_batch_updates])
               
               failed_records = still_failed
               attempt += 1
            
            if failed_records:
               final_failed_ids = [r.get("record_id") for r in failed_records]
               logger.error(f"经过三轮重试后，仍有 {len(failed_records)} 条记录处理失败: {final_failed_ids}")

        
        logger.info(f"批量生成完成 - 成功: {success_count}, 跳过: {skip_count}, 失败: {error_count}, 配额不足跳过: {quota_skip_count}")
        
        msg = "批量生成完成"
        if quota_skip_count > 0:
            msg = f"批量生成完成。因配额不足,有{quota_skip_count}条记录被跳过,请充值后续处理。"

        return jsonify({
            "code": 0,
            "msg": msg,
            "data": {
               "total": total,
               "success": success_count,
               "skipped": skip_count,
               "quota_skipped": quota_skip_count,
               "failed": error_count
            }
        })
    except Exception as e:
        logger.error(f"批量生成失败: {e}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/proxy/image', methods=['GET'])
def proxy_image():
    """代理下载飞书图片 (保留用于兼容)"""
    try:
        file_token = request.args.get('file_token')
        app_token = request.args.get('app_token')
        if not file_token:
            return jsonify({"code": 400, "msg": "Missing file_token"}), 400
            
        lark_client = current_app.config['LARK_CLIENT']
        image_content = lark_client.download_file(file_token, app_token=app_token)
        
        from flask import Response
        return Response(image_content, mimetype='image/png')
    except Exception as e:
        logger.error(f"Proxy image failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/proxy/file', methods=['GET'])
def proxy_file():
    """代理下载飞书文件 (支持各种类型)"""
    try:
        file_token = request.args.get('file_token')
        file_name = request.args.get('name', 'file')
        app_token = request.args.get('app_token')
        if not file_token:
            return jsonify({"code": 400, "msg": "Missing file_token"}), 400
            
        lark_client = current_app.config['LARK_CLIENT']
        file_content = lark_client.download_file(file_token, app_token=app_token)
        
        import mimetypes
        mimetype, _ = mimetypes.guess_type(file_name)
        if not mimetype:
            mimetype = 'application/octet-stream'
            
        from flask import Response
        response = Response(file_content, mimetype=mimetype)
        
        # 对于非图片/PDF文件,强制下载
        # 对于图片/PDF,允许浏览器在线预览
        is_previewable = mimetype.startswith('image/') or mimetype == 'application/pdf'
        disposition = 'inline' if is_previewable else 'attachment'
        
        response.headers['Content-Disposition'] = f'{disposition}; filename="{file_name}"'
        return response
    except Exception as e:
        logger.error(f"Proxy file failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

# === 支付相关接口 ===

PACKAGES = {
    # 年度订阅
    'plan_year_1': {'amount': 990.0, 'quota': 0, 'years': 1, 'name': '1年无限次订阅'},
    'plan_year_2': {'amount': 1683.0, 'quota': 0, 'years': 2, 'name': '2年无限次订阅(85折)'},
    'plan_year_3': {'amount': 2376.0, 'quota': 0, 'years': 3, 'name': '3年无限次订阅(8折)'},
    # 单独额度
    'plan_quota_1000': {'amount': 399.0, 'quota': 1000, 'years': 0, 'name': '1000次额度包'},
    'plan_quota_3500': {'amount': 699.0, 'quota': 3500, 'years': 0, 'name': '3500次额度包'},
    'plan_quota_25000': {'amount': 3699.0, 'quota': 25000, 'years': 0, 'name': '25000次额度包'},
    
    # 兼容旧的前端测试包
    'plan_5': {'amount': 0.1, 'quota': 5, 'years': 0, 'name': '5次测试包'},
    'plan_500': {'amount': 19.9, 'quota': 500, 'years': 0, 'name': '500次套餐'},
    'plan_1000': {'amount': 35.0, 'quota': 1000, 'years': 0, 'name': '1000次套餐'},
    'plan_5000': {'amount': 119.0, 'quota': 5000, 'years': 0, 'name': '5000次套餐'},
    'plan_10000': {'amount': 209.0, 'quota': 10000, 'years': 0, 'name': '10000次套餐'},
    'plan_50000': {'amount': 939.0, 'quota': 50000, 'years': 0, 'name': '50000次套餐'},
    'plan_100000': {'amount': 1739.0, 'quota': 100000, 'years': 0, 'name': '100000次套餐'},
    'plan_200000': {'amount': 3199.0, 'quota': 200000, 'years': 0, 'name': '200000次套餐'},
}

def load_packages_config():
    import os
    import json
    # 默认兜底套餐配置 (与 PACKAGES 一致)
    default_packages = {
        'plan_year_test': {'amount': 0.01, 'quota': 30, 'days': 1, 'billing_type': 'duration', 'name': '试用授权 (1天)'},
        'plan_year_1': {'amount': 990.0, 'quota': 0, 'days': 365, 'billing_type': 'duration', 'name': '1年无限次订阅'},
        'plan_year_2': {'amount': 1683.0, 'quota': 0, 'days': 730, 'billing_type': 'duration', 'name': '2年无限次订阅(85折)'},
        'plan_year_3': {'amount': 2376.0, 'quota': 0, 'days': 1095, 'billing_type': 'duration', 'name': '3年无限次订阅(8折)'},
        'plan_quota_1000': {'amount': 399.0, 'quota': 1000, 'days': 0, 'billing_type': 'quota', 'name': '1000次额度包'},
        'plan_quota_3500': {'amount': 699.0, 'quota': 3500, 'days': 0, 'billing_type': 'quota', 'name': '3500次额度包'},
        'plan_quota_25000': {'amount': 3699.0, 'quota': 25000, 'days': 0, 'billing_type': 'quota', 'name': '25000次额度包'},
    }
    try:
        if os.path.exists("packages.json"):
            with open("packages.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                plans = data.get("plans", [])
                packages = {}
                for plan in plans:
                    pid = plan.get("plan_id")
                    if pid:
                        packages[pid] = {
                            'amount': float(plan.get("price", 0)),
                            'quota': int(plan.get("quota", 0)),
                            'days': int(plan.get("days", 0)),
                            'billing_type': plan.get("billing_type", "quota"),
                            'name': plan.get("name", pid)
                        }
                return packages
    except Exception as e:
        logger.error(f"Failed to load packages.json: {e}")
    return default_packages

@api_bp.route('/pay/pricing', methods=['GET'])
def get_public_pricing():
    """获取公开的计费方案列表（供前端动态加载使用）"""
    try:
        packages = load_packages_config()
        plans = []
        for pid, p in packages.items():
            # 过滤掉调试用的 plan_year_test 以保持前台界面简洁
            if pid == "plan_year_test":
                continue
            billing_type = p.get("billing_type", "quota")
            amount = float(p.get("amount", p.get("price", 0)))
            quota = p.get("quota", 0)
            days = p.get("days", 0)
            name = p.get("name", pid)
            
            p_type = "year" if billing_type == "duration" else "quota"
            
            # 格式化价格
            price_val = int(amount) if amount.is_integer() else amount
            price_str = f"{price_val}元"
            
            # 计算年份或单元介绍
            years_val = days // 365 if days > 0 else 0
            
            # 根据 plan_id 或内容匹配对应的描述与标签，从而完美对齐原本的原型设计
            tag = ""
            desc = ""
            if pid == "plan_year_1":
                desc = "全功能无限使用，高频首选"
            elif pid == "plan_year_2":
                tag = "85折"
                desc = "省 297 元，长期更划算"
            elif pid == "plan_year_3":
                tag = "8折"
                desc = "省 594 元，省心无忧"
            elif pid == "plan_quota_1000":
                desc = "约 0.399 元/次，中低频使用"
            elif pid == "plan_quota_3500":
                desc = "约 0.200 元/次，超值推荐"
            elif pid == "plan_quota_25000":
                desc = "约 0.148 元/次，大型企业首选"
            else:
                # 动态计算自定义包的介绍
                if p_type == "year":
                    desc = f"有效期 {days} 天，全功能不限次使用"
                else:
                    unit_cost = (amount / quota) if quota > 0 else 0
                    desc = f"约 {unit_cost:.3f} 元/次，企业量身定制额度"
            
            plan_item = {
                "id": pid,
                "type": p_type,
                "quota": quota,
                "price": price_str,
                "label": name,
                "desc": desc
            }
            if tag:
                plan_item["tag"] = tag
            if years_val > 0:
                plan_item["years"] = years_val
                
            plans.append(plan_item)
            
        return jsonify({"code": 0, "plans": plans})
    except Exception as e:
        logger.error(f"Failed to get public pricing: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/pay/create', methods=['POST'])
def create_pay_order():
    """
    功能描述：创建支付订单，马某。
    @param (HTTP Request Body): tenant_key - 租户 Key; package_id - 套餐规格 ID
    @return: json 订单数据或错误消息与状态码
    """
    try:
        data = request.json
        tenant_key = data.get('tenant_key')
        package_id = data.get('package_id')
        pay_type = data.get('pay_type', 'wechat')
        
        if not tenant_key or not package_id:
            return jsonify({"code": 400, "msg": "参数缺失: tenant_key 和 package_id 必填"}), 400
            
        # 已移除根据金蝶连接器方案相同的企业登记后台双重校验逻辑，马某。
            
        packages = load_packages_config()
        if package_id not in packages:
            return jsonify({"code": 400, "msg": "无效的套餐类型"}), 400
            
        plan = packages[package_id]
        amount = plan['amount']
        added_quota = plan.get('quota', 0)
        added_days = plan.get('days', 0)
        plan_name = plan.get('name', package_id)
            
        order_id = f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid4())[:8]}"
        
        quota_service = current_app.config['QUOTA_SERVICE']
        wechat_pay_service = current_app.config['WECHAT_PAY_SERVICE']
        
        # 1. 在本地数据库创建 PENDING 订单
        success = quota_service.create_payment_order(
            order_id, tenant_key, package_id, pay_type, amount, added_quota, added_days
        )
        
        if not success:
            return jsonify({"code": 500, "msg": "创建订单数据失败"}), 500
            
        # 2. 调用支付平台接口获取二维码链接
        if pay_type == 'wechat':
            code_url = wechat_pay_service.create_native_order(
               order_id, amount, f"电子签名插件-{plan_name}"
            )
            if not code_url:
               return jsonify({"code": 500, "msg": "对接微信支付失败,请检查后台配置(如私钥文件)"}), 500
               
            return jsonify({
               "code": 0,
               "data": {
                   "order_id": order_id,
                   "code_url": code_url
               }
            })
        else:
            return jsonify({"code": 400, "msg": "目前仅支持微信支付"}), 400
            
    except Exception as e:
        logger.error(f"Error in create_pay_order: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/pay/wechat-notify', methods=['POST'])
def wechat_notify():
    """微信支付回调"""
    # 微信支付要求返回 200 或其他指定格式
    try:
        # 从 Flask 忽略大小写的 header 对象中精确提取微信要求的 4 个字段
        clean_headers = {
            'Wechatpay-Signature': request.headers.get('Wechatpay-Signature'),
            'Wechatpay-Timestamp': request.headers.get('Wechatpay-Timestamp'),
            'Wechatpay-Nonce': request.headers.get('Wechatpay-Nonce'),
            'Wechatpay-Serial': request.headers.get('Wechatpay-Serial')
        }
        
        body = request.get_data(as_text=True)
        
        # 强制将收到的请求头和 body 写入专门的调试文件
        import datetime
        import traceback
        try:
            with open("wechat_debug_log.txt", "a", encoding="utf-8") as f:
               f.write(f"\n[{datetime.datetime.now()}] WECHAT NOTIFY HIT!\n")
               f.write(f"Headers: {dict(request.headers)}\n")
               f.write(f"Body: {body}\n")
        except Exception:
            logger.error("Failed to write wechat_debug_log.txt")
            logger.error(traceback.format_exc())
        
        wechat_pay_service = current_app.config['WECHAT_PAY_SERVICE']
        quota_service = current_app.config['QUOTA_SERVICE']
        
        resource = wechat_pay_service.verify_callback(clean_headers, body)
        if resource:
            order_id = resource.get('out_trade_no')
            transaction_id = resource.get('transaction_id')
            trade_state = resource.get('trade_state')
            
            if trade_state == 'SUCCESS':
               # 更新订单状态并充值
               quota_service.update_payment_status(order_id, 'SUCCESS', transaction_id)
               logger.info(f"Payment SUCCESS confirmed for order {order_id}")
            
            return jsonify({"code": "SUCCESS", "message": "OK"}), 200
        else:
            logger.warning("WeChat callback verification failed")
            return jsonify({"code": "FAIL", "message": "Sign Error"}), 400
            
    except Exception as e:
        logger.error(f"Error in wechat_notify: {e}")
        return jsonify({"code": "FAIL", "message": str(e)}), 500

@api_bp.route('/pay/status/<order_id>', methods=['GET'])
def get_payment_status(order_id):
    """查询支付订单状态 (增加主动对账逻辑)"""
    try:
        quota_service = current_app.config['QUOTA_SERVICE']
        wechat_pay_service = current_app.config['WECHAT_PAY_SERVICE']
        
        # 1. 先查本地数据库
        status = quota_service.get_payment_status(order_id)
        
        # 2. 如果本地是 PENDING，则主动去微信后台查一次（解决回调延迟问题）
        if status == 'PENDING':
            query_result = wechat_pay_service.query_order(order_id)
            if query_result:
               trade_state = query_result.get('trade_state')
               logger.info(f"Polling check - Order: {order_id} | WeChat State: {trade_state}")
               
               if trade_state == 'SUCCESS':
                   transaction_id = query_result.get('transaction_id')
                   # 发现已成功，同步本地状态并增加配额
                   quota_service.update_payment_status(order_id, 'SUCCESS', transaction_id)
                   status = 'SUCCESS'
                   logger.info(f"Active Query SUCCESS: Order {order_id} is now SUCCESS")
        
        if status:
            return jsonify({"code": 0, "status": status})
        else:
            return jsonify({"code": 404, "msg": "订单不存在"}), 404
    except Exception as e:
        logger.error(f"Error in get_payment_status: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/pay/mock-success/<order_id>', methods=['GET', 'POST'])
@test_route_only
def mock_pay_success(order_id):
    """模拟支付成功"""
    try:
        from uuid import uuid4
        quota_service = current_app.config['QUOTA_SERVICE']
        success = quota_service.update_payment_status(order_id, 'SUCCESS', f"MOCK_TX_{uuid4().hex[:12]}")
        if success:
            return jsonify({"code": 0, "msg": "Mock payment success simulated successfully"})
        else:
            return jsonify({"code": 500, "msg": "Failed to update payment status"}), 500
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/pay/debug-logs', methods=['GET'])
@test_route_only
def get_debug_logs():
    """临时诊断接口:读取后端运行日志"""
    try:
        import os
        log_paths = [
            'wechat_debug_log.txt', 
            '/www/wwwroot/feishu_api_sgin/wechat_debug_log.txt', 
            '/www/wwwlogs/sign-pri.anhuishuzhi.com.log',
            '/www/wwwlogs/sign-pri.anhuishuzhi.com.error.log',
            'backend.log', 
            'nohup.out'
        ]
        logs = {}
        for path in log_paths:
            if os.path.exists(path):
               with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                   # 取最后 100 行
                   logs[path] = "".join(f.readlines()[-100:])
            else:
               logs[path] = "Not Found"
               
        # 获取回调失败的原始尝试(如果记录了的话)
        return jsonify({"code": 0, "logs": logs})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})


# ==========================================
# 安汇数字管理平台 (ahsz-plugin-platform) 对接适配接口
# ==========================================

def check_api_token(f):
    import os
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        expected_token = os.getenv("API_TOKEN")
        if not expected_token:
            return jsonify({"code": 500, "msg": "Configuration error: API_TOKEN environment variable must be set"}), 500
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"code": 401, "msg": "Missing or invalid token format"}), 401
        token = auth_header.split(" ")[1]
        if token != expected_token:
            return jsonify({"code": 403, "msg": "Invalid authorization token"}), 403
        return f(*args, **kwargs)
    return decorated


@api_bp.route('/health', methods=['GET'])
@check_api_token
def health_check():
    """系统健康状况与动态资源负载上报"""
    try:
        raw_cpu = _proc.cpu_percent(interval=None)
        cpu = round(raw_cpu / psutil.cpu_count(), 1)
    except Exception:
        cpu = 0.1
    try:
        mem = round(_proc.memory_percent(), 2)
    except Exception:
        mem = 1.0
    return jsonify({
        "status": "healthy",
        "cpu_usage": cpu,
        "memory_usage": mem
    })


@api_bp.route('/plugin/billing/config', methods=['GET'])
@check_api_token
def get_billing_config():
    """获取计费方案配置"""
    try:
        import os
        import json
        # 使用绝对路径，防止进程工作目录不一致导致读取不到，马某。
        packages_json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packages.json")
        if os.path.exists(packages_json_path):
            with open(packages_json_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
    except Exception as e:
        logger.error(f"Failed to read packages.json: {e}")

    config = {
        "schema_version": 1,
        "revision": 1,
        "currency": "CNY",
        "plans": [
            {
                "plan_id": "plan_year_test",
                "name": "试用授权 (1天)",
                "billing_type": "duration",
                "days": 1,
                "price": 0.01,
                "enabled": True
            },
            {
                "plan_id": "plan_year_1",
                "name": "1年无限次订阅",
                "billing_type": "duration",
                "days": 365,
                "price": 990.0,
                "enabled": True
            },
            {
                "plan_id": "plan_year_2",
                "name": "2年无限次订阅(85折)",
                "billing_type": "duration",
                "days": 730,
                "price": 1683.0,
                "enabled": True
            },
            {
                "plan_id": "plan_year_3",
                "name": "3年无限次订阅(8折)",
                "billing_type": "duration",
                "days": 1095,
                "price": 2376.0,
                "enabled": True
            },
            {
                "plan_id": "plan_quota_1000",
                "name": "1000次额度包",
                "billing_type": "quota",
                "quota": 1000,
                "price": 399.0,
                "enabled": True
            },
            {
                "plan_id": "plan_quota_3500",
                "name": "3500次额度包",
                "billing_type": "quota",
                "quota": 3500,
                "price": 699.0,
                "enabled": True
            },
            {
                "plan_id": "plan_quota_25000",
                "name": "25000次额度包",
                "billing_type": "quota",
                "quota": 25000,
                "price": 3699.0,
                "enabled": True
            }
        ]
    }
    return jsonify(config)


@api_bp.route('/plugin/billing/update', methods=['POST'])
@check_api_token
def update_billing_config():
    """更新计费方案配置"""
    try:
        data = request.json
        import json
        import os
        # 使用绝对路径，防止进程工作目录不一致导致写入到其他地方，马某。
        packages_json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packages.json")
        with open(packages_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"[Platform Billing Sync] Saved billing config to packages.json")
        return jsonify({"code": 0, "msg": "Billing config updated successfully"})
    except Exception as e:
        logger.error(f"Failed to update billing config: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@api_bp.route('/plugin/license/sync', methods=['POST'])
@check_api_token
def sync_license():
    """同步租户授权状态 (由平台统一发放/重置/回滚时触发)"""
    data = request.json
    tenant_key = data.get("tenant_key")
    status = data.get("status")
    expire_time_raw = data.get("expire_time")
    max_quota = data.get("max_quota")
    used_quota = data.get("used_quota")
    billing_type = data.get("billing_type", "quota")
    
    if not tenant_key:
        return jsonify({"code": 400, "msg": "Missing tenant_key"}), 400
        
    quota_service = current_app.config['QUOTA_SERVICE']
    now = datetime.now()
    
    # 转换时间到 datetime 对象
    expire_time = None
    if expire_time_raw:
        try:
            # 优先尝试按 "YYYY-MM-DD HH:mm:ss" 格式解析
            expire_time = datetime.strptime(expire_time_raw, "%Y-%m-%d %H:%M:%S")
        except Exception:
            try:
                # 兼容毫秒时间戳格式
                expire_time = datetime.fromtimestamp(int(expire_time_raw) / 1000)
            except Exception as e:
                logger.error(f"Failed to parse expire_time: {expire_time_raw} | {e}")
            
    try:
        # 检测企业是否存在于当前数据库中
        row = quota_service._execute_query("SELECT tenant_key FROM tenant_quota WHERE tenant_key = %s", (tenant_key,), fetch_one=True)
        if row:
            quota_service._execute_query(
                "UPDATE tenant_quota SET total_quota = %s, used_quota = %s, expire_time = %s, billing_type = %s, updated_at = %s WHERE tenant_key = %s",
                (max_quota if max_quota is not None else 30, used_quota if used_quota is not None else 0, expire_time, billing_type, now, tenant_key), commit=True
            )
        else:
            quota_service._execute_query(
                "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, expire_time, billing_type, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (tenant_key, max_quota if max_quota is not None else 30, used_quota if used_quota is not None else 0, expire_time, billing_type, now, now), commit=True
            )
        logger.info(f"[Platform Sync] License updated for tenant: {tenant_key} | max_quota={max_quota}, expire_time={expire_time}, billing_type={billing_type}")
        return jsonify({"code": 0, "msg": "License synced successfully"})
    except Exception as e:
        logger.error(f"Failed to sync license for tenant {tenant_key}: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@api_bp.route('/plugin/order/refund', methods=['POST'])
@check_api_token
def refund_order():
    """通知插件端某笔订单已退款并扣减配额，通过单连接事务和行锁保证原子性与幂等性"""
    import os
    data = request.json or {}
    order_id = data.get("order_id")
    status = data.get("status")
    refund_quota = data.get("refund_quota", 0)
    refund_days = data.get("refund_days", 0)
    
    if not order_id or not status:
        return jsonify({"code": 400, "msg": "Missing order_id or status"}), 400
        
    quota_service = current_app.config['QUOTA_SERVICE']
    conn = quota_service._get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            # 1. 行锁锁定订单记录
            cursor.execute(
                "SELECT tenant_key, status FROM payment_orders WHERE order_id = %s FOR UPDATE",
                (order_id,)
            )
            row_order = cursor.fetchone()

            if not row_order:
                conn.rollback()
                return jsonify({"code": 404, "msg": "Order not found"}), 404
                
            tenant_key, current_status = row_order
            
            # 2. 幂等性检测：若订单状态已经是 REFUNDED，直接提交并成功返回，不进行重复扣减
            if current_status == "REFUNDED":
                conn.commit()
                return jsonify({"code": 0, "msg": "Order already refunded (idempotent)"})
                
            # 3. 扣减授权配额/时长
            if refund_quota > 0 or refund_days > 0:
                cursor.execute(
                    "SELECT total_quota, expire_time FROM tenant_quota WHERE tenant_key = %s FOR UPDATE",
                    (tenant_key,)
                )
                row_quota = cursor.fetchone()
                if row_quota:
                    total_quota, expire_time = row_quota
                    if refund_quota > 0:
                        new_total = total_quota - refund_quota
                        if new_total < 0:
                            new_total = 0
                        cursor.execute(
                            "UPDATE tenant_quota SET total_quota = %s, updated_at = %s WHERE tenant_key = %s",
                            (new_total, datetime.now(), tenant_key)
                        )
                    elif refund_days > 0 and expire_time:
                        try:
                            if isinstance(expire_time, datetime):
                                expire_dt = expire_time
                            else:
                                expire_dt = datetime.fromisoformat(expire_time)
                            new_expire = expire_dt - timedelta(days=refund_days)
                            cursor.execute(
                                "UPDATE tenant_quota SET expire_time = %s, updated_at = %s WHERE tenant_key = %s",
                                (new_expire, datetime.now(), tenant_key)
                            )
                        except Exception as ex:
                            logger.error(f"Error parsing expire_time: {ex}")

            # 4. 更新订单状态为 REFUNDED
            cursor.execute(
                "UPDATE payment_orders SET status = %s, updated_at = %s WHERE order_id = %s",
                (status, datetime.now(), order_id)
            )
            
        conn.commit()
        logger.info(f"[Platform Sync] Order refunded and service retracted successfully. order_id={order_id}")
        return jsonify({"code": 0, "msg": "Order refunded and service retracted successfully"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to refund order {order_id} atomically: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500
    finally:
        conn.close()

