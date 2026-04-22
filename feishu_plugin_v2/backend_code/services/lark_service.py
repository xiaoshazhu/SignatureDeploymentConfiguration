import logging
import io
import os
from baseopensdk import BaseClient
from baseopensdk.api.base.v1 import *
from baseopensdk.api.drive.v1 import *
from utils.qrcode_utils import generate_qrcode as generate_qr_image
from utils.rate_limiter import feishu_api_limiter, retry_on_rate_limit

from baseopensdk.api.base.v1.model.app_table_field import AppTableField
from typing import Any

# 猴子补丁: 解决 SDK 无法处理 Bitable API 返回的字符串类型 description 的问题
# 在某些情况下, description 是字符串而非对象, 导致 SDK 反序列化失败
AppTableField._types['description'] = Any

logger = logging.getLogger(__name__)

class LarkClient:
    def __init__(self, app_id, app_secret, personal_base_token=None, app_token=None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token or "" # 默认 app_token
        
        # 优先从本地文件加载已保存的授权码
        self.token_file = ".personal_base_token"
        if not personal_base_token and os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    personal_base_token = f.read().strip()
                logger.info("Loaded personal_base_token from local file")
            except Exception as e:
                logger.error(f"Failed to load token from file: {e}")

        self.personal_base_token = personal_base_token
        self._init_client()

    def _init_client(self):
        """初始化或重新初始化 BaseClient"""
        builder = BaseClient.builder()
        if self.personal_base_token:
            builder.personal_base_token(self.personal_base_token)
        
        # 必须设置 app_token,否则内部构建URL会报错
        builder.app_token(self.app_token)
            
        self.client = builder.build()
        logger.info(f"LarkClient initialized (Token present: {bool(self.personal_base_token)})")

    def set_personal_base_token(self, token):
        """动态设置并保存授权码"""
        if not token:
            return
        
        self.personal_base_token = token
        # 保存到本地文件以供下次启动使用
        try:
            with open(self.token_file, 'w') as f:
                f.write(token)
            logger.info("Saved personal_base_token to local file")
        except Exception as e:
            logger.error(f"Failed to save token to file: {e}")
            
        self._init_client()

    def _get_tenant_access_token(self):
        """兼容旧代码,如果需要的话可以返回None或抛错。目前SDK自动处理鉴权"""
        return None

    @retry_on_rate_limit(max_retries=3, initial_delay=1, backoff_factor=2, max_delay=10)
    def upload_image(self, app_token, image_bytes, file_name='signature.png'):
        """上传图片到飞书 Drive"""
        feishu_api_limiter.acquire()
        
        self.client._config.app_token = app_token
        f = io.BytesIO(image_bytes)
        request = UploadAllMediaRequest.builder() \
            .request_body(UploadAllMediaRequestBody.builder() \
                .file_name(file_name) \
                .parent_type("bitable_file") \
                .parent_node(app_token) \
                .size(len(image_bytes)) \
                .file(f) \
                .build()) \
            .build()
        
        response = self.client.drive.v1.media.upload_all(request)
        
        if response.success():
            file_token = response.data.file_token
            logger.info(f"成功上传图片: {file_name}, file_token: {file_token}")
            return file_token
        else:
            logger.error(f"Upload failed: {response.code} {response.msg}")
            raise Exception(f"Upload failed: {response.msg}")


    def get_bitable_fields(self, app_token, table_id):
        """获取多维表格的所有字段信息"""
        self.client._config.app_token = app_token
        request = ListAppTableFieldRequest.builder() \
            .table_id(table_id) \
            .build()
        
        response = self.client.base.v1.app_table_field.list(request)
        
        if response.success():
            items = response.data.items
            field_map = {}
            for field in items:
                field_name = field.field_name
                field_id = field.field_id
                if field_name and field_id:
                    field_map[field_name] = field_id
            logger.info(f"获取到 {len(field_map)} 个字段")
            return field_map
        else:
            logger.error(f"获取字段列表失败: {response.code} {response.msg}")
            return {}

    def get_field_meta_list(self, app_token, table_id):
        """获取多维表格的字段元数据列表"""
        self.client._config.app_token = app_token
        request = ListAppTableFieldRequest.builder() \
            .table_id(table_id) \
            .build()
        
        response = self.client.base.v1.app_table_field.list(request)
        
        if response.success():
            return [f.__dict__ for f in response.data.items] # 转为字典以保持兼容
        else:
            logger.error(f"获取字段元数据失败: {response.code} {response.msg}")
            return []


    def get_bitable_record(self, app_token, table_id, record_id):
        """获取多维表格记录"""
        self.client._config.app_token = app_token
        request = GetAppTableRecordRequest.builder() \
            .table_id(table_id) \
            .record_id(record_id) \
            .build()
        
        response = self.client.base.v1.app_table_record.get(request)
        if response.success():
            # 需要转为字典以保持兼容
            record = response.data.record
            return {"record_id": record.record_id, "fields": record.fields}
        else:
            logger.error(f"Get record failed: {response.code} {response.msg}")
            raise Exception(f"Get record failed: {response.msg}")

    @retry_on_rate_limit(max_retries=3, initial_delay=1, backoff_factor=2, max_delay=10)
    def update_bitable_record(self, app_token, table_id, record_id, fields):
        """更新多维表格记录"""
        feishu_api_limiter.acquire()
        
        self.client._config.app_token = app_token
        request = UpdateAppTableRecordRequest.builder() \
            .table_id(table_id) \
            .record_id(record_id) \
            .request_body(AppTableRecord.builder() \
                .fields(fields) \
                .build()) \
            .build()
        
        response = self.client.base.v1.app_table_record.update(request)
        if response.success():
            record = response.data.record
            return {"record_id": record.record_id, "fields": record.fields}
        else:
            logger.error(f"Update record failed: {response.code} {response.msg}")
            raise Exception(f"Update record failed: {response.msg}")

    def update_record(self, app_token, table_id, record_id, fields):
        """更新记录(update_bitable_record 的别名方法)
        
        为了兼容不同的调用方式,提供此别名方法
        """
        return self.update_bitable_record(app_token, table_id, record_id, fields)

    def get_records(self, app_token, table_id, page_size=500):
        """获取多维表格所有记录(支持分页提取所有)"""
        self.client._config.app_token = app_token
        all_items = []
        page_token = None
        
        while True:
            builder = ListAppTableRecordRequest.builder() \
                .table_id(table_id) \
                .page_size(page_size)
                
            if page_token:
                builder.page_token(page_token)
                
            request = builder.build()
            response = self.client.base.v1.app_table_record.list(request)
            
            if response.success():
                items = response.data.items
                if items:
                    all_items.extend([{"record_id": it.record_id, "fields": it.fields} for it in items])
                    
                if response.data.has_more:
                    page_token = response.data.page_token
                else:
                    break
            else:
                logger.error(f"List records failed: {response.code} {response.msg}")
                raise Exception(f"List records failed: {response.msg}")
                
        return all_items

    def search_records(self, app_token, table_id, filter_conditions):
        """搜索记录"""
        self.client._config.app_token = app_token
        request = SearchAppTableRecordRequest.builder() \
            .table_id(table_id) \
            .request_body(SearchAppTableRecordRequestBody.builder() \
                .filter(filter_conditions) \
                .page_size(10) \
                .build()) \
            .build()
        
        response = self.client.base.v1.app_table_record.search(request)
        if response.success():
            items = response.data.items
            return [{"record_id": it.record_id, "fields": it.fields} for it in items]
        else:
            logger.error(f"Search records failed: {response.code} {response.msg}")
            raise Exception(f"Search records failed: {response.msg}")

    def generate_qrcode(self, url: str, app_token: str) -> str:
        """生成二维码并上传到飞书
        
        Args:
            url: 要生成二维码的URL
            app_token: 多维表格的app_token
            
        Returns:
            str: 上传成功后的file_token
        """
        try:
            # 生成二维码图片
            qr_bytes = generate_qr_image(url)
            
            # 上传到飞书
            file_token = self.upload_image(app_token, qr_bytes, 'qrcode.png')
            logger.info(f"成功生成并上传二维码,URL: {url[:50]}...")
            
            return file_token
        except Exception as e:
            logger.error(f"生成二维码失败: {e}")
            raise

    def download_file(self, file_token):
        """下载文件"""
        request = DownloadMediaRequest.builder() \
            .file_token(file_token) \
            .build()
        
        response = self.client.drive.v1.media.download(request)
        if response.success():
            return response.file.read()
        else:
            logger.error(f"Download file failed: {response.code} {response.msg}")
            raise Exception(f"Download file failed: {response.msg}")
