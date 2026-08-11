import logging
from services.lark_service import LarkClient
from utils.image_utils import decode_base64_image

logger = logging.getLogger(__name__)

class SignService:
    def __init__(self, lark_client: LarkClient, sign_archive_table_id):
        self.lark_client = lark_client
        self.sign_archive_table_id = sign_archive_table_id

    def get_sign_info(self, app_token, table_id, record_id, user_id=None, sign_config=None):
        """获取签字页初始化信息
        
        需求11: 如果已签字,返回签名图片列表
        需求8: 支持URL参数配置(sign_config)
        
        Args:
            sign_config: URL参数配置 {"mode": "或签/会签", "count": 3}
        """
        # 1. 获取当前行数据
        record = self.lark_client.get_bitable_record(app_token, table_id, record_id)
        fields = record.get("fields", {})
        
        # 2. 检查并处理所有附件字段 (不仅仅是签字附件)
        processed_fields = {}
        for key, value in fields.items():
            is_att = False
            att_list = []
            
            # 情况1: 列表格式 (标准附件字段)
            if isinstance(value, list) and len(value) > 0:
                # 检查列表项是否包含任何类似 token 的键
                first_item = value[0]
                if isinstance(first_item, dict):
                    token_keys = ["file_token", "attachmentToken", "token", "fileToken"]
                    if any(tk in first_item for tk in token_keys):
                        is_att = True
                        att_list = value
            
            # 情况2: 字符串格式 (公式、引用或旧版 API)
            elif isinstance(value, str) and value.strip().startswith('['):
                try:
                    import json
                    parsed = json.loads(value)
                    if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                        token_keys = ["file_token", "attachmentToken", "token", "fileToken"]
                        if any(tk in parsed[0] for tk in token_keys):
                            is_att = True
                            att_list = parsed
                except:
                    pass

            if is_att:
                logger.info(f"识别到附件字段: {key}")
                new_value = []
                for att in att_list:
                    if isinstance(att, dict):
                        # 获取可能的 token
                        file_token = att.get("file_token") or att.get("attachmentToken") or att.get("token") or att.get("fileToken")
                        if file_token:
                            att_copy = att.copy()
                            # 统一为前端使用的 file_token 和 url
                            att_copy["file_token"] = file_token
                            att_copy["url"] = f"proxy/file?file_token={file_token}&name={att.get('name', 'file')}&app_token={app_token}"
                            new_value.append(att_copy)
                processed_fields[key] = new_value
            # 情况3: 超链接对象 (识别为字典且包含 link/url 和 text)
            elif isinstance(value, dict) and ("link" in value or "url" in value) and "text" in value:
                processed_fields[key] = value
            
            # 情况4: 字符串格式的超链接 (更宽松的识别逻辑)
            elif isinstance(value, str) and value.strip().startswith('{'):
                val_strip = value.strip()
                val_lower = val_strip.lower()
                if ("link" in val_lower or "url" in val_lower) and "text" in val_lower:
                    try:
                        import json
                        parsed = json.loads(val_strip)
                        if isinstance(parsed, dict) and ("link" in parsed or "url" in parsed) and "text" in parsed:
                            processed_fields[key] = parsed
                        else:
                            processed_fields[key] = value
                    except:
                        processed_fields[key] = value
                else:
                    processed_fields[key] = value
            else:
                processed_fields[key] = value

        # 3. 检查历史签名 (已按需关闭)
        has_history = False
        history_token = None

        # 4. 构造返回数据
        # 使用字段名称直接获取(根据飞书官方文档)
        title = fields.get("合同名称") or fields.get("标题") or "未命名文档"
        status = fields.get("签字状态", "待签字")
        
        # 需求11: 如果已签字,获取签名图片列表
        signature_images = []
        if status == "已签字":
            attachments = processed_fields.get("签字附件", [])
            for att in attachments:
                if isinstance(att, dict):
                    signature_images.append({
                        "file_token": att.get("file_token"),
                        "url": att.get("url"),
                        "name": att.get("name", "签名")
                    })
        
        result = {
            "title": title,
            "status": status,
            "row_data": processed_fields,
            "has_history_sign": has_history,
            "history_sign_token": history_token,
            "signature_images": signature_images  # 需求11: 返回签名图片列表
        }
        
        # 需求8: 如果有URL参数配置,返回给前端
        if sign_config:
            result["sign_config"] = sign_config
            logger.info(f"返回URL参数配置: {sign_config}")
        
        return result

    def submit_sign(self, app_token, table_id, record_id, data):
        """提交签名
        
        实现功能:
        1. 上传签名图片到飞书
        2. 更新签字附件列
        3. 更新签字入口列状态文本(请点击签字 → 签字中(X/Y) → 已签字)
        4. 更新状态列(未签字 → 已签字)
        5. 生成并上传签字入口二维码
        
        需求12: 防重复提交校验
        """
        # 需求12: 提交前检查当前状态,防止重复提交
        record = self.lark_client.get_bitable_record(app_token, table_id, record_id)
        fields = record.get("fields", {})
        current_status = fields.get("签字状态", "")
        
        # 如果已经是"已签字"状态,拒绝提交
        if current_status == "已签字":
            logger.warning(f"记录 {record_id} 已被签署,拒绝重复提交")
            raise ValueError("此记录已被他人签署,请刷新页面查看")
        
        user_id = data.get("user_id")
        sign_type = data.get("sign_type")  # new or reuse
        
        # 1. 获取 File Token
        file_token = None
        # 历史签名功能已关闭, 统一使用新签名逻辑
        image_base64 = data.get("image_base64")
        if not image_base64:
            raise ValueError("Missing image data")
        image_bytes = decode_base64_image(image_base64)
        # 上传签名图片,传入app_token
        file_token = self.lark_client.upload_image(app_token, image_bytes, 'signature.png')
        logger.info(f"上传新签名成功: {file_token}")
            
        # 历史存档逻辑已关闭

        if not file_token:
            raise ValueError("Failed to get file token")

        # 2. 获取当前行数据以判断逻辑
        record = self.lark_client.get_bitable_record(app_token, table_id, record_id)
        fields = record.get("fields", {})
        current_attachments = fields.get("签字附件", [])
        
        # 3. 判断逻辑 (优先使用前端传入的配置参数)
        # 需求8: 从参数获取配置,而不是依赖表格列
        sign_mode = data.get("sign_mode") or fields.get("签字模式", "或签")
        sign_count_config = data.get("sign_count") or fields.get("需签字人数", 1)
        
        try:
            total_needed = int(sign_count_config)
        except (ValueError, TypeError):
            total_needed = 1
            
        logger.info(f"签字模式: {sign_mode}, 需签字人数: {total_needed}")
        
        new_attachments = []
        link_text = ""  # 签字入口列的显示文本
        status_value = ""  # 状态列的值
        
        if sign_mode == "会签":
            # 追加模式
            new_attachments = current_attachments + [{"file_token": file_token}]
            
            # 检查人数
            current_count = len(new_attachments)
            
            logger.info(f"会签进度: {current_count}/{total_needed}")
            
            if current_count < total_needed:
                link_text = f"签字中({current_count}/{total_needed})"
                status_value = "未签字"  # 会签进行中保持未签字状态
            else:
                link_text = "已签字"
                status_value = "已签字"
        else:
            # 或签 (覆盖模式)
            new_attachments = [{"file_token": file_token}]
            link_text = "已签字"
            status_value = "已签字"
            logger.info("或签模式,覆盖签名")

        # 4. 获取当前签字入口的URL
        current_link_obj = fields.get("签字确认", {})
        sign_url = ""
        
        if isinstance(current_link_obj, dict):
            sign_url = current_link_obj.get("link", "")
        elif isinstance(current_link_obj, str):
            # 如果是字符串,说明是纯URL
            sign_url = current_link_obj
        
        logger.info(f"签字入口URL: {sign_url[:50] if sign_url else 'None'}...")
        
        # 5. 生成并上传二维码
        qr_token = None
        if sign_url:
            try:
                qr_token = self.lark_client.generate_qrcode(sign_url, app_token)
                logger.info(f"成功生成二维码: {qr_token}")
            except Exception as e:
                logger.warning(f"生成二维码失败,继续执行: {e}")
        
        # 6. 更新记录 - 使用字段名称(根据飞书官方文档)
        update_fields = {
            "签字附件": new_attachments,
            "签字状态": status_value  # 单选字段,直接传字符串值
        }
        
        # 更新签字入口列 (超链接字段)
        if sign_url:
            update_fields["签字确认"] = {
                "text": link_text,
                "link": sign_url
            }
        
        # 更新签字二维码列 (附件字段)
        if qr_token:
            update_fields["签字二维码"] = [{"file_token": qr_token}]
        
        logger.info(f"准备更新记录,字段: {list(update_fields.keys())}")
        
        # 执行更新
        self.lark_client.update_bitable_record(app_token, table_id, record_id, update_fields)
        
        logger.info(f"签字提交成功 - record_id: {record_id}, 状态: {link_text}")
        
        return {
            "status": link_text,
            "sign_mode": sign_mode,
            "attachments_count": len(new_attachments)
        }
