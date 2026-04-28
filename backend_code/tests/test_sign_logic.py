import unittest
from unittest.mock import MagicMock
from services.sign_service import SignService

class TestSignService(unittest.TestCase):
    def setUp(self):
        self.mock_lark_client = MagicMock()
        self.sign_service = SignService(self.mock_lark_client, "mock_table_id")

    def test_or_sign_logic(self):
        # 模拟“或签”场景
        self.mock_lark_client.upload_image.return_value = "new_token"
        self.mock_lark_client.get_bitable_record.return_value = {
            "fields": {
                "签字模式": "或签",
                "签字附件": [{"file_token": "old_token"}]
            }
        }
        
        data = {
            "user_id": "u1",
            "sign_type": "new",
            "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        }
        
        result = self.sign_service.submit_sign("app_token", "table_id", "record_id", data)
        
        # 验证结果
        self.assertEqual(result["status"], "✅ 已签字")
        
        # 验证调用参数
        self.mock_lark_client.update_bitable_record.assert_called_once()
        call_args = self.mock_lark_client.update_bitable_record.call_args
        update_fields = call_args[0][3]
        
        # 或签应该是覆盖附件
        self.assertEqual(len(update_fields["签字附件"]), 1)
        self.assertEqual(update_fields["签字附件"][0]["file_token"], "new_token")

    def test_and_sign_logic_progress(self):
        # 模拟“会签”场景 - 进度更新
        self.mock_lark_client.upload_image.return_value = "new_token"
        self.mock_lark_client.get_bitable_record.return_value = {
            "fields": {
                "签字模式": "会签",
                "需签字人数": 3,
                "签字附件": [{"file_token": "token1"}]
            }
        }
        
        data = {
            "user_id": "u2",
            "sign_type": "new",
            "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        }
        
        result = self.sign_service.submit_sign("app_token", "table_id", "record_id", data)
        
        # 验证结果: 1+1=2, 总3, 所以是 2/3
        self.assertEqual(result["status"], "📝 签字中 (2/3)")
        
        # 验证附件追加
        call_args = self.mock_lark_client.update_bitable_record.call_args
        update_fields = call_args[0][3]
        self.assertEqual(len(update_fields["签字附件"]), 2)

    def test_and_sign_logic_complete(self):
        # 模拟“会签”场景 - 完成
        self.mock_lark_client.upload_image.return_value = "new_token"
        self.mock_lark_client.get_bitable_record.return_value = {
            "fields": {
                "签字模式": "会签",
                "需签字人数": 2,
                "签字附件": [{"file_token": "token1"}]
            }
        }
        
        data = {
            "user_id": "u2",
            "sign_type": "new",
            "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        }
        
        result = self.sign_service.submit_sign("app_token", "table_id", "record_id", data)
        
        # 验证结果: 1+1=2, 总2, 所以是完成
        self.assertEqual(result["status"], "✅ 已签字")

if __name__ == '__main__':
    unittest.main()
