#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书签字插件 - 字段重命名迁移脚本

功能: 将已有表格中的"✍️ 签字入口"字段重命名为"签字确认"

使用方法:
1. 确保已安装依赖: pip install requests python-dotenv
2. 配置环境变量(.env文件):
   - APP_ID: 飞书应用ID
   - APP_SECRET: 飞书应用密钥
3. 运行脚本: python migrate_field_name.py <app_token> <table_id>

注意事项:
- 此操作不可逆,请先备份数据
- 建议先在测试表格中验证
- 如果表格中不存在"✍️ 签字入口"字段,脚本会跳过
"""

import os
import sys
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

APP_ID = os.getenv('APP_ID')
APP_SECRET = os.getenv('APP_SECRET')

class FieldMigrator:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
    
    def get_tenant_access_token(self):
        """获取tenant_access_token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"获取token失败: {result.get('msg')}")
        
        self.access_token = result.get("tenant_access_token")
        print(f"✓ 成功获取access_token")
        return self.access_token
    
    def get_field_list(self, app_token, table_id):
        """获取表格字段列表"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"获取字段列表失败: {result.get('msg')}")
        
        fields = result.get("data", {}).get("items", [])
        print(f"✓ 成功获取字段列表,共{len(fields)}个字段")
        return fields
    
    def rename_field(self, app_token, table_id, field_id, new_name):
        """重命名字段"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "field_name": new_name
        }
        
        response = requests.put(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"重命名字段失败: {result.get('msg')}")
        
        print(f"✓ 成功重命名字段: {new_name}")
        return result
    
    def migrate(self, app_token, table_id):
        """执行迁移"""
        print(f"\n开始迁移表格: {app_token}/{table_id}")
        print("=" * 60)
        
        # 1. 获取token
        self.get_tenant_access_token()
        
        # 2. 获取字段列表
        fields = self.get_field_list(app_token, table_id)
        
        # 3. 查找"✍️ 签字入口"字段
        old_field_name = "✍️ 签字入口"
        new_field_name = "签字确认"
        target_field = None
        
        for field in fields:
            if field.get("field_name") == old_field_name:
                target_field = field
                break
        
        if not target_field:
            print(f"\n⚠️  未找到字段 '{old_field_name}',无需迁移")
            return False
        
        field_id = target_field.get("field_id")
        print(f"\n找到目标字段:")
        print(f"  - 字段名称: {old_field_name}")
        print(f"  - 字段ID: {field_id}")
        print(f"  - 字段类型: {target_field.get('type')}")
        
        # 4. 确认操作
        print(f"\n即将重命名为: {new_field_name}")
        confirm = input("确认执行? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("\n✗ 用户取消操作")
            return False
        
        # 5. 执行重命名
        self.rename_field(app_token, table_id, field_id, new_field_name)
        
        print("\n" + "=" * 60)
        print("✓ 迁移完成!")
        return True

def main():
    if len(sys.argv) < 3:
        print("使用方法: python migrate_field_name.py <app_token> <table_id>")
        print("\n示例:")
        print("  python migrate_field_name.py bascnxxxxxx tblxxxxxx")
        sys.exit(1)
    
    app_token = sys.argv[1]
    table_id = sys.argv[2]
    
    if not APP_ID or not APP_SECRET:
        print("错误: 请先配置环境变量 APP_ID 和 APP_SECRET")
        sys.exit(1)
    
    try:
        migrator = FieldMigrator(APP_ID, APP_SECRET)
        migrator.migrate(app_token, table_id)
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
