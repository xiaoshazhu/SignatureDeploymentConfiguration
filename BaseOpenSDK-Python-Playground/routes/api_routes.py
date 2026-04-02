from flask import Blueprint, request, jsonify, current_app
import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from utils.crypto_utils import encrypt_url_params, decrypt_url_params

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# 辅助函数:脱敏app_token
def mask_token(token):
    """脱敏token,只显示前8个字符"""
    if not token:
        return "None"
    return token[:8] + "..." if len(token) > 8 else token

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

def generate_sign_link_for_record(lark_client, app_token, table_id, record_id, frontend_host, sign_mode='或签', sign_count=3, enable_qrcode=True):
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
        
    Returns:
        dict: 包含 sign_url 和 qr_token 的字典
        
    Raises:
        Exception: 生成失败时抛出异常
    """
    import time
    import random
    
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
    
    # 生成二维码
    qr_token = None
    if enable_qrcode:
        try:
            qr_token = lark_client.generate_qrcode(sign_url, app_token)
            logger.info(f"二维码生成成功 - record_id: {record_id}")
        except Exception as e:
            logger.warning(f"生成二维码失败 - record_id: {record_id}, 错误: {e}")
    else:
        logger.info(f"跳过二维码生成 - record_id: {record_id}")
    
    # 字段名称(根据飞书官方文档)
    sign_link_field_name = "签字确认"
    status_field_name = "签字状态"
    qrcode_field_name = "签字二维码"
    
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
    
    logger.info(f"准备更新记录 {record_id}, 字段: {list(update_fields.keys())}")
    lark_client.update_bitable_record(app_token, table_id, record_id, update_fields)
    
    return {
        "sign_url": sign_url,
        "qr_token": qr_token
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
        
        # 从 app config 获取 lark_client
        lark_client = current_app.config['LARK_CLIENT']
        
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
        frontend_host = data.get('frontend_host')
        sign_mode = data.get('sign_mode', '或签')
        sign_count = data.get('sign_count', 3)
        enable_qrcode = data.get('enable_qrcode', True) # 需求: 获取二维码开关状态
        
        logger.info(f"收到单行生成请求 - table_id: {table_id}, record_id: {record_id}, mode: {sign_mode}, count: {sign_count}, enable_qrcode: {enable_qrcode}")
        logger.info(f"参数详情 - app_token: {mask_token(app_token)}, frontend_host: {frontend_host}")
        
        if not all([app_token, table_id, record_id, frontend_host]):
            missing = []
            if not app_token: missing.append('app_token')
            if not table_id: missing.append('table_id')
            if not record_id: missing.append('record_id')
            if not frontend_host: missing.append('frontend_host')
            logger.error(f"缺少必需参数: {', '.join(missing)}")
            return jsonify({"code": 400, "msg": f"Missing required parameters: {', '.join(missing)}"}), 400
        
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
            enable_qrcode=enable_qrcode
        )
        
        logger.info(f"单行链接生成成功 - record_id: {record_id}")
        
        return jsonify({
            "code": 0,
            "msg": "生成成功",
            "data": {
                "sign_url": result['sign_url'],
                "qr_token": result['qr_token'],
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
        frontend_host = data.get('frontend_host')
        
        # 需求8: 获取批量配置参数
        sign_mode = data.get('sign_mode', '或签')
        sign_count = data.get('sign_count', 3)
        enable_qrcode = data.get('enable_qrcode', True) # 需求: 获取二维码开关状态
        
        if not app_token or not table_id or not frontend_host:
            return jsonify({"code": 400, "msg": "Missing required parameters"}), 400
        
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
        
        # 1. 获取所有记录ID
        records = lark_client.get_records(app_token, table_id)
        total = len(records)
        logger.info(f"获取到 {total} 条记录")
        
        # 2. 批量处理每条记录 - 使用并发优化
        import os
        from concurrent.futures import ThreadPoolExecutor, as_completed

        success_count = 0
        skip_count = 0
        error_count = 0
        
        # 字段名称(根据飞书官方文档,后端API使用字段名称而不是field_id)
        sign_link_field_name = "签字确认"
        status_field_name = "签字状态"
        qrcode_field_name = "签字二维码"
        
        # 检查表格是否存在二维码列
        field_map = lark_client.get_bitable_fields(app_token, table_id)
        has_qrcode_field = qrcode_field_name in field_map
        logger.info(f"表格字段检查 - 存在二维码列: {has_qrcode_field}")
        
        # 过滤需要处理的记录
        records_to_process = []
        for record in records:
            fields = record.get("fields", {})
            existing_link = fields.get(sign_link_field_name)
            if existing_link:
                skip_count += 1
            else:
                records_to_process.append(record)
        
        logger.info(f"需要处理 {len(records_to_process)} 条记录,跳过 {skip_count} 条")
        
        # 定义线程安全的处理函数
        def process_single_record(record):
            """处理单条记录的线程安全函数"""
            record_id = record.get("record_id")
            try:
                # 使用封装的函数生成链接
                result = generate_sign_link_for_record(
                    lark_client=lark_client,
                    app_token=app_token,
                    table_id=table_id,
                    record_id=record_id,
                    frontend_host=frontend_host,
                    sign_mode=sign_mode,
                    sign_count=sign_count,
                    enable_qrcode=enable_qrcode
                )
                return ('success', record_id)
            except Exception as e:
                logger.error(f"处理记录失败 - record_id: {record_id}, 错误: {e}")
                return ('error', record_id, str(e))
        
        # 使用线程池并发处理
        # 降低并发度,配合限流器使用,避免触发API频率限制
        max_workers = min(5, len(records_to_process))
        logger.info(f"使用 {max_workers} 个线程并发处理 (已启用API限流器)")
        
        if len(records_to_process) > 0:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_record = {
                    executor.submit(process_single_record, record): record 
                    for record in records_to_process
                }
                
                # 收集结果
                completed = 0
                for future in as_completed(future_to_record):
                    result = future.result()
                    completed += 1
                    
                    if result[0] == 'success':
                        success_count += 1
                    else:
                        error_count += 1
                    
                    # 每5条记录或最后一条输出进度
                    if completed % 5 == 0 or completed == len(records_to_process):
                        logger.info(
                            f"处理进度: {completed}/{len(records_to_process)} "
                            f"(成功: {success_count}, 失败: {error_count})"
                        )

        
        logger.info(f"批量生成完成 - 成功: {success_count}, 跳过: {skip_count}, 失败: {error_count}")
        
        return jsonify({
            "code": 0,
            "msg": "批量生成完成",
            "data": {
                "total": total,
                "success": success_count,
                "skipped": skip_count,
                "failed": error_count
            }
        })
    except Exception as e:
        logger.error(f"批量生成失败: {e}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500

@api_bp.route('/proxy/image', methods=['GET'])
def proxy_image():
    """代理下载飞书图片"""
    try:
        file_token = request.args.get('file_token')
        if not file_token:
            return jsonify({"code": 400, "msg": "Missing file_token"}), 400
            
        lark_client = current_app.config['LARK_CLIENT']
        image_content = lark_client.download_file(file_token)
        
        from flask import Response
        return Response(image_content, mimetype='image/png')
    except Exception as e:
        logger.error(f"Proxy image failed: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500
