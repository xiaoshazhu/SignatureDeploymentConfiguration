import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class QuotaService:
    def __init__(self, db_path='quota.db'):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库表结构"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tenant_quota (
                        tenant_key TEXT PRIMARY KEY,
                        total_quota INTEGER DEFAULT 30,
                        used_quota INTEGER DEFAULT 0,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                ''')
                # 记录购买历史
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS purchase_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_key TEXT,
                        package_name TEXT,
                        added_quota INTEGER,
                        amount REAL,
                        created_at TIMESTAMP
                    )
                ''')
                conn.commit()
            logger.info("Quota database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize quota database: {e}")

    def get_quota_info(self, tenant_key):
        """获取租户配额信息"""
        if not tenant_key:
            return None
            
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT total_quota, used_quota FROM tenant_quota WHERE tenant_key = ?", (tenant_key,))
                row = cursor.fetchone()
                
                if row:
                    total, used = row
                    return {
                        "total": total,
                        "used": used,
                        "remaining": total - used
                    }
                else:
                    # 如果不存在,则初始化免费试用
                    return self.init_free_trial(tenant_key)
        except Exception as e:
            logger.error(f"Error getting quota for {tenant_key}: {e}")
            return None

    def init_free_trial(self, tenant_key):
        """初始化 30 次免费试用"""
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (tenant_key, 30, 0, now, now)
                )
                conn.commit()
            logger.info(f"Initialized free trial (30) for tenant: {tenant_key}")
            return {"total": 30, "used": 0, "remaining": 30}
        except sqlite3.IntegrityError:
            # 已存在则直接返回
            return self.get_quota_info(tenant_key)
        except Exception as e:
            logger.error(f"Failed to init free trial for {tenant_key}: {e}")
            return None

    def check_quota(self, tenant_key, required_count=1):
        """校验配额是否足够"""
        info = self.get_quota_info(tenant_key)
        if not info:
            return False
            
        return info["remaining"] >= required_count

    def consume_quota(self, tenant_key, count=1):
        """扣除配额"""
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tenant_quota SET used_quota = used_quota + ?, updated_at = ? WHERE tenant_key = ?",
                    (count, now, tenant_key)
                )
                if cursor.rowcount == 0:
                    # 如果记录不存在（理论上不应该，因为 init_free_trial 会先被调用）
                    self.init_free_trial(tenant_key)
                    cursor.execute(
                        "UPDATE tenant_quota SET used_quota = used_quota + ?, updated_at = ? WHERE tenant_key = ?",
                        (count, now, tenant_key)
                    )
                conn.commit()
            logger.info(f"Consumed {count} quota for tenant: {tenant_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to consume quota for {tenant_key}: {e}")
            return False

    def recharge_quota(self, tenant_key, package_name, added_quota, amount):
        """充值/增加配额"""
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 检查是否存在
                cursor.execute("SELECT total_quota FROM tenant_quota WHERE tenant_key = ?", (tenant_key,))
                if cursor.fetchone():
                    cursor.execute(
                        "UPDATE tenant_quota SET total_quota = total_quota + ?, updated_at = ? WHERE tenant_key = ?",
                        (added_quota, now, tenant_key)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (tenant_key, added_quota, 0, now, now)
                    )
                
                # 记录购买历史
                cursor.execute(
                    "INSERT INTO purchase_history (tenant_key, package_name, added_quota, amount, created_at) VALUES (?, ?, ?, ?, ?)",
                    (tenant_key, package_name, added_quota, amount, now)
                )
                conn.commit()
            logger.info(f"Recharged {added_quota} for {tenant_key}, package: {package_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to recharge quota for {tenant_key}: {e}")
            return False
