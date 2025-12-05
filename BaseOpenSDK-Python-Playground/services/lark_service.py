import requests
import json
import time
import os
import logging
from utils.qrcode_utils import generate_qrcode as generate_qr_image
from utils.rate_limiter import feishu_api_limiter, retry_on_rate_limit

logger = logging.getLogger(__name__)

class LarkClient:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None
        self.token_expire_time = 0

    def _get_tenant_access_token(self):
        """获取或刷新 tenant_access_token"""
        now = time.time()
        if self.token and now < self.token_expire_time - 60: # 提前60秒刷新
            return self.token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            resp_json = response.json()
            
            if resp_json.get("code") == 0:
                self.token = resp_json.get("tenant_access_token")
                self.token_expire_time = now + resp_json.get("expire", 7200)
                logger.info("Successfully refreshed tenant_access_token")
                return self.token
            else:
                logger.error(f"Failed to get token: {resp_json}")
                raise Exception(f"Failed to get token: {resp_json.get('msg')}")
        except Exception as e:
            logger.error(f"Error getting token: {e}")
            raise

    @retry_on_rate_limit(max_retries=3, initial_delay=1, backoff_factor=2, max_delay=10)
    def upload_image(self, app_token, image_bytes, file_name='signature.png'):
        """上传图片到飞书 Drive
        
        Args:
            app_token: 多维表格的app_token
            image_bytes: 图片字节数据
            file_name: 文件名,默认为signature.png
            
        Returns:
            str: 上传成功后的file_token
        """
        # 限流控制:获取令牌后才能继续
        feishu_api_limiter.acquire()
        
        token = self._get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # 使用 bitable_file 类型,需要提供 parent_node (app_token)
        # 注意: multipart/form-data 格式要求
        files = {
            'file_name': (None, file_name),
            'parent_type': (None, 'bitable_file'),
            'parent_node': (None, app_token),
            'size': (None, str(len(image_bytes))),
            'file': (file_name, image_bytes, 'image/png')  # 文件内容
        }
        
        try:
            response = requests.post(url, headers=headers, files=files)
            resp_json = response.json()
            
            if resp_json.get("code") == 0:
                file_token = resp_json.get("data", {}).get("file_token")
                logger.info(f"成功上传图片: {file_name}, file_token: {file_token}")
                return file_token
            else:
                logger.error(f"Upload failed: {resp_json}")
                raise Exception(f"Upload failed: {resp_json.get('msg')}")
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            raise


    def get_bitable_fields(self, app_token, table_id):
        """获取多维表格的所有字段信息
        
        Returns:
            dict: 字段名到field_id的映射 {"签字入口": "fld123", ...}
        """
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            resp_json = response.json()
            
            if resp_json.get("code") == 0:
                fields = resp_json.get("data", {}).get("items", [])
                # 创建字段名到field_id的映射
                field_map = {}
                for field in fields:
                    field_name = field.get("field_name")
                    field_id = field.get("field_id")
                    field_type = field.get("type")
                    if field_name and field_id:
                        field_map[field_name] = field_id
                        logger.debug(f"字段: {field_name} -> {field_id} (类型: {field_type})")
                
                logger.info(f"获取到 {len(field_map)} 个字段: {list(field_map.keys())}")
                return field_map
            else:
                logger.error(f"获取字段列表失败: {resp_json}")
                return {}
        except Exception as e:
            logger.error(f"Error getting fields: {e}")
            return {}

    def get_field_meta_list(self, app_token, table_id):
        """获取多维表格的字段元数据列表
        
        Returns:
            list: 字段元数据列表 [{"field_id": "fld123", "field_name": "签字入口", "type": 1}, ...]
        """
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            resp_json = response.json()
            
            if resp_json.get("code") == 0:
                fields = resp_json.get("data", {}).get("items", [])
                logger.info(f"获取到 {len(fields)} 个字段元数据")
                return fields
            else:
                logger.error(f"获取字段元数据列表失败: {resp_json}")
                return []
        except Exception as e:
            logger.error(f"Error getting field meta list: {e}")
            return []


    def get_bitable_record(self, app_token, table_id, record_id):

        """获取多维表格记录"""
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            resp_json = response.json()
            
            if resp_json.get("code") == 0:
                return resp_json.get("data", {}).get("record", {})
            else:
                logger.error(f"Get record failed: {resp_json}")
                raise Exception(f"Get record failed: {resp_json.get('msg')}")
        except Exception as e:
            logger.error(f"Error getting record: {e}")
            raise

    @retry_on_rate_limit(max_retries=3, initial_delay=1, backoff_factor=2, max_delay=10)
    def update_bitable_record(self, app_token, table_id, record_id, fields):
        """更新多维表格记录"""
        # 限流控制:获取令牌后才能继续
        feishu_api_limiter.acquire()
        
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        data = {
            "fields": fields
        }
        
        try:
            response = requests.put(url, headers=headers, json=data)
            resp_json = response.json()
            
            if resp_json.get("code") == 0:
                return resp_json.get("data", {}).get("record", {})
            else:
                logger.error(f"Update record failed: {resp_json}")
                raise Exception(f"Update record failed: {resp_json.get('msg')}")
        except Exception as e:
            logger.error(f"Error updating record: {e}")
            raise

    def update_record(self, app_token, table_id, record_id, fields):
        """更新记录(update_bitable_record 的别名方法)
        
        为了兼容不同的调用方式,提供此别名方法
        """
        return self.update_bitable_record(app_token, table_id, record_id, fields)

    def search_records(self, app_token, table_id, filter_conditions):
        """搜索记录 (用于查找历史签名)"""
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        data = {
            "filter": filter_conditions,
            "page_size": 10
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            resp_json = response.json()
            
            if resp_json.get("code") == 0:
                return resp_json.get("data", {}).get("items", [])
            else:
                logger.error(f"Search records failed: {resp_json}")
                raise Exception(f"Search records failed: {resp_json.get('msg')}")
        except Exception as e:
            logger.error(f"Error searching records: {e}")
            raise

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
        """下载文件
        
        Args:
            file_token: 文件 token
            
        Returns:
            bytes: 文件内容
        """
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Download file failed: {response.json()}")
                raise Exception(f"Download file failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise
