import pymysql
import os
import logging
from datetime import datetime, timedelta
from queue import Queue, Empty
import threading

logger = logging.getLogger(__name__)

class MySQLConnectionPool:
    def __init__(self, creator, max_connections=10):
        self.creator = creator
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        self.active_connections = 0

    def get_connection(self):
        try:
            # Try to get an idle connection from the pool without blocking
            conn = self.pool.get(block=False)
            try:
                conn.ping(reconnect=True)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = self.creator()
            return PooledConnection(self, conn)
        except Empty:
            # No idle connection, check if we can create a new one
            with self.lock:
                if self.active_connections < self.max_connections:
                    try:
                        conn = self.creator()
                        self.active_connections += 1
                        return PooledConnection(self, conn)
                    except Exception as e:
                        raise e
            # If we're at max connections, wait for one to become available
            try:
                conn = self.pool.get(block=True, timeout=5)
                try:
                    conn.ping(reconnect=True)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = self.creator()
                return PooledConnection(self, conn)
            except Empty:
                raise Exception("MySQL connection pool exhausted. No connection available within 5 seconds.")

    def release_connection(self, conn):
        if conn is None:
            return
        try:
            self.pool.put(conn, block=False)
        except Exception:
            with self.lock:
                self.active_connections -= 1
            try:
                conn.close()
            except Exception:
                pass

class PooledConnection:
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if not self._closed:
            self._closed = True
            self._pool.release_connection(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self._conn.rollback()
            else:
                self._conn.commit()
        finally:
            self.close()

class QuotaService:
    def __init__(self, db_path=None):
        # db_path is ignored because we are now using MySQL
        self.pool = MySQLConnectionPool(
            creator=self._create_new_connection,
            max_connections=int(os.getenv("DB_MAX_CONNECTIONS", 64))
        )
        self._init_db()

    def _create_new_connection(self):
        db_password = os.getenv("DB_PASSWORD")
        if not db_password:
            raise Exception("Configuration error: DB_PASSWORD environment variable must be set.")
            
        return pymysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=db_password,
            database=os.getenv("DB_NAME", "electronic_signature"),
            charset='utf8mb4'
        )

    def _get_connection(self):
        return self.pool.get_connection()

    def _execute_query(self, query, params=(), commit=False, fetch_one=False, fetch_all=False):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if commit:
                    conn.commit()
                if fetch_one:
                    return cursor.fetchone()
                if fetch_all:
                    return cursor.fetchall()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Database query execution failed: {query} | Error: {e}")
            raise e
        finally:
            conn.close()

    def _init_db(self):
        """验证数据库连接并确保基本表和视图存在"""
        try:
            row = self._execute_query("SHOW TABLES LIKE 'tenant_quota'", fetch_one=True)
            if not row:
                logger.warning("tenant_quota table not found, please run init_mysql.sql initialization script")
            else:
                logger.info("MySQL database connection successfully verified")
        except Exception as e:
            logger.error(f"Failed to verify MySQL database: {e}")

    @property
    def auto_trial(self):
        """动态读取 app_config.json 配置，马某"""
        try:
            import json
            # 获取当前文件所在目录的父目录中的 app_config.json
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app_config.json')
            # 兼容服务器上的绝对路径
            if not os.path.exists(config_path):
                config_path = '/www/wwwroot/feishu_api_sign/app_config.json'
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return bool(config.get('auto_trial', False))
        except Exception as e:
            logger.error(f"Failed to read app_config.json: {e}")
        return False

    def init_free_trial_with_30(self, tenant_key):
        """自动分配30次试用额度并写入数据库，马某"""
        now = datetime.now()
        try:
            self._execute_query(
                "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, billing_type, has_claimed_trial, created_at, updated_at) VALUES (%s, 30, 0, 'quota', 1, %s, %s)",
                (tenant_key, now, now), commit=True
            )
            logger.info(f"Automatically initialized 30 free trial credits for tenant: {tenant_key}")
            return {
                "total": 30,
                "used": 0,
                "remaining": 30,
                "is_subscribed": False,
                "expire_time": None,
                "has_claimed_trial": True,
                "auto_trial": True
            }
        except pymysql.err.IntegrityError:
            # 并发情况下防止重复插入，直接获取已有状态
            return self.get_quota_info(tenant_key)
        except Exception as e:
            logger.error(f"Failed to automatically init free trial for {tenant_key}: {e}")
            return None

    def get_quota_info(self, tenant_key):
        """获取租户配额信息"""
        if not tenant_key:
            return None
            
        try:
            row = self._execute_query(
                "SELECT total_quota, used_quota, expire_time, billing_type, has_claimed_trial FROM tenant_quota WHERE tenant_key = %s",
                (tenant_key,), fetch_one=True
            )
            
            if row:
                total, used, expire_time, billing_type, has_claimed_trial = row
                
                # 检查是否订阅了年费
                is_subscribed = False
                if billing_type == 'duration' and expire_time:
                    try:
                        if isinstance(expire_time, datetime):
                            expire_dt = expire_time
                        else:
                            expire_dt = datetime.fromisoformat(expire_time)
                        if expire_dt > datetime.now():
                            is_subscribed = True
                    except Exception:
                        pass
                
                expire_time_str = expire_time.isoformat() if isinstance(expire_time, datetime) else expire_time
                return {
                    "total": total,
                    "used": used,
                    "remaining": 999999 if is_subscribed else (total - used),
                    "is_subscribed": is_subscribed,
                    "expire_time": expire_time_str,
                    "has_claimed_trial": bool(has_claimed_trial),
                    "auto_trial": self.auto_trial
                }
            else:
                # 如果开启了自动分配，则执行老版本初始化30次逻辑，马某
                if self.auto_trial:
                    return self.init_free_trial_with_30(tenant_key)
                    
                # 如果不存在,则返回零配额虚拟状态，不自动在数据库创建记录，马某。
                return {
                    "total": 0,
                    "used": 0,
                    "remaining": 0,
                    "is_subscribed": False,
                    "expire_time": None,
                    "has_claimed_trial": False,
                    "auto_trial": self.auto_trial
                }
        except Exception as e:
            logger.error(f"Error getting quota for {tenant_key}: {e}")
            return None

    def init_tenant_quota(self, tenant_key):
        """初始化新企业账号为 0 配额"""
        now = datetime.now()
        try:
            self._execute_query(
                "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, billing_type, has_claimed_trial, created_at, updated_at) VALUES (%s, 0, 0, 'quota', 0, %s, %s)",
                (tenant_key, now, now), commit=True
            )
            logger.info(f"Initialized zero-quota account for tenant: {tenant_key}")
            return {"total": 0, "used": 0, "remaining": 0, "is_subscribed": False, "expire_time": None, "has_claimed_trial": False}
        except pymysql.err.IntegrityError:
            return self.get_quota_info(tenant_key)
        except Exception as e:
            logger.error(f"Failed to init tenant quota for {tenant_key}: {e}")
            return None

    def init_free_trial(self, tenant_key):
        """兼容函数：初始化 0 次免费试用"""
        return self.init_tenant_quota(tenant_key)

    def claim_free_trial(self, tenant_key):
        """手动领取 30 次免费体验配额（加入严格防刷防重复逻辑）"""
        if not tenant_key:
            raise ValueError("租户 Key 不能为空")

        info = self.get_quota_info(tenant_key)
        if not info:
            raise ValueError("初始化租户账户失败")

        # 1. 严格校验是否已领用过
        if info.get("has_claimed_trial"):
            raise ValueError("当前企业已领取过免费试用，无法重复领取")

        # 2. 严格校验是否已购买过正式授权（非零配额或年费订阅）
        if info.get("total") > 0 or info.get("is_subscribed"):
            raise ValueError("当前企业已激活或购买过正式授权，无法领取试用")

        now = datetime.now()
        try:
            # 检查数据库中是否存在记录
            row = self._execute_query(
                "SELECT tenant_key FROM tenant_quota WHERE tenant_key = %s",
                (tenant_key,), fetch_one=True
            )
            if row:
                self._execute_query(
                    "UPDATE tenant_quota SET total_quota = total_quota + 30, has_claimed_trial = 1, updated_at = %s WHERE tenant_key = %s",
                    (now, tenant_key), commit=True
                )
            else:
                self._execute_query(
                    "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, billing_type, has_claimed_trial, created_at, updated_at) "
                    "VALUES (%s, 30, 0, 'quota', 1, %s, %s)",
                    (tenant_key, now, now), commit=True
                )
            logger.info(f"Tenant {tenant_key} successfully claimed 30 free trial credits.")
            return True
        except Exception as e:
            logger.error(f"Failed to claim free trial for tenant {tenant_key}: {e}")
            raise e

    def check_quota(self, tenant_key, required_count=1):
        """校验配额是否足够"""
        info = self.get_quota_info(tenant_key)
        if not info:
            return False
            
        return info["remaining"] >= required_count

    def consume_quota(self, tenant_key, count=1):
        """扣除配额 (原子防超扣设计)"""
        now = datetime.now()
        
        # 如果当前有生效 of 年费订阅，则直接免除额度次数消耗
        info = self.get_quota_info(tenant_key)
        if info and info.get("is_subscribed"):
            logger.info(f"[QUOTA AUDIT] Tenant: {tenant_key} | 年费订阅期内，免除额度次数消耗")
            return True
            
        try:
            # 🌟 原子安全扣费并支持年费到期自动重置为 quota 计费，马某
            rowcount = self._execute_query(
                "UPDATE tenant_quota SET used_quota = used_quota + %s, billing_type = 'quota', updated_at = %s "
                "WHERE tenant_key = %s "
                "AND (billing_type = 'quota' OR (billing_type = 'duration' AND expire_time <= %s)) "
                "AND used_quota + %s <= total_quota",
                (count, now, tenant_key, now, count), commit=True
            )
            
            if rowcount == 0:
                # 检查是否因为不存在记录，或者是因为额度已满
                row = self._execute_query("SELECT tenant_key FROM tenant_quota WHERE tenant_key = %s", (tenant_key,), fetch_one=True)
                if not row:
                    # 如果开启了自动体验，则静默初始化 30 次，然后尝试扣减，马某
                    if self.auto_trial:
                        self.init_free_trial_with_30(tenant_key)
                        rowcount = self._execute_query(
                            "UPDATE tenant_quota SET used_quota = used_quota + %s, billing_type = 'quota', updated_at = %s "
                            "WHERE tenant_key = %s "
                            "AND (billing_type = 'quota' OR (billing_type = 'duration' AND expire_time <= %s)) "
                            "AND used_quota + %s <= total_quota",
                            (count, now, tenant_key, now, count), commit=True
                        )
                        if rowcount == 1:
                            return True
                    
                    # 记录不存在，且当前处于“完善企业登记信息才可领用”模式下，因此无法在此静默初始化和扣除，马某。
                    logger.warning(f"[QUOTA AUDIT] Tenant: {tenant_key} | Account record not found. User must claim trial manually.")
                    return False
            
            if rowcount == 1:
                new_info = self.get_quota_info(tenant_key)
                logger.info(f"[QUOTA AUDIT] Tenant: {tenant_key} | Consumed: {count} | Remaining: {new_info['remaining'] if new_info else 'Unknown'}")
                return True
            else:
                logger.warning(f"[QUOTA AUDIT] Tenant: {tenant_key} | Atomic consume failed: Insufficient quota or invalid state")
                return False
        except Exception as e:
            logger.error(f"Failed to consume quota for {tenant_key}: {e}")
            return False

    def recharge_quota(self, tenant_key, package_name, added_quota, amount, package_id=None, added_days=0):
        """为租户充值额度或增加订阅授权天数"""
        import json
        now = datetime.now()
        
        # Load packages config dynamically to support added/modified packages
        packages = {}
        # 默认兜底配置
        default_packages = {
            'plan_year_test': {'quota': 30, 'days': 1, 'billing_type': 'duration', 'name': '试用授权 (1天)'},
            'plan_year_1': {'quota': 0, 'days': 365, 'billing_type': 'duration', 'name': '年度订阅 (1年)'},
            'plan_year_2': {'quota': 0, 'days': 730, 'billing_type': 'duration', 'name': '进阶授权 (2年)'},
            'plan_year_3': {'quota': 0, 'days': 1095, 'billing_type': 'duration', 'name': '尊享授权 (3年)'},
            'plan_quota_100': {'quota': 100, 'days': 0, 'billing_type': 'quota', 'name': '100次授权包'},
            'plan_quota_500': {'quota': 500, 'days': 0, 'billing_type': 'quota', 'name': '500次授权包'},
            'plan_quota_1000': {'quota': 1000, 'days': 0, 'billing_type': 'quota', 'name': '1000次授权包'},
        }
        
        try:
            if os.path.exists("packages.json"):
                with open("packages.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    plans = data.get("plans", [])
                    for plan in plans:
                        pid = plan.get("plan_id")
                        if pid:
                            packages[pid] = {
                                'quota': int(plan.get("quota", 0)),
                                'days': int(plan.get("days", 0)),
                                'billing_type': plan.get("billing_type", "quota"),
                                'name': plan.get("name", pid)
                            }
        except Exception as e:
            logger.error(f"Failed to load packages.json in recharge_quota: {e}")
            
        # Merge defaults if not present
        for pid, val in default_packages.items():
            if pid not in packages:
                packages[pid] = val

        # Match package info
        is_subscription = False
        days_to_add = added_days
        quota_to_add = added_quota

        if package_id and package_id in packages:
            plan = packages[package_id]
            if plan['billing_type'] == 'duration':
                is_subscription = True
                days_to_add = added_days if added_days > 0 else plan['days']
            else:
                is_subscription = False
                quota_to_add = added_quota if added_quota > 0 else plan['quota']
        else:
            # Fallback legacy logic by parsing package_name or using hardcoded defaults
            if package_id:
                if package_id == 'plan_year_test':
                    is_subscription = True
                    days_to_add = 1
                elif package_id == 'plan_year_1':
                    is_subscription = True
                    days_to_add = 365
                elif package_id == 'plan_year_2':
                    is_subscription = True
                    days_to_add = 730
                elif package_id == 'plan_year_3':
                    is_subscription = True
                    days_to_add = 1095
            elif package_name:
                if '1天' in package_name:
                    is_subscription = True
                    days_to_add = 1
                elif '1年' in package_name:
                    is_subscription = True
                    days_to_add = 365
                elif '2年' in package_name:
                    is_subscription = True
                    days_to_add = 730
                elif '3年' in package_name:
                    is_subscription = True
                    days_to_add = 1095

        conn = self._get_connection()
        try:
            conn.begin()
            with conn.cursor() as cursor:
                # 1. 锁行查询：使用 SELECT ... FOR UPDATE 锁定当前租户记录，防止并发订单重合覆盖
                cursor.execute(
                    "SELECT total_quota, expire_time FROM tenant_quota WHERE tenant_key = %s FOR UPDATE",
                    (tenant_key,)
                )
                row = cursor.fetchone()
                
                if row:
                    total_quota, expire_time = row
                    if is_subscription:
                        # 计算新过期时间
                        current_expire = None
                        if expire_time:
                            try:
                                if isinstance(expire_time, datetime):
                                    current_expire = expire_time
                                else:
                                    current_expire = datetime.fromisoformat(expire_time)
                            except Exception:
                                pass
                        
                        # 如果存在且未过期，在过期时间上叠加；否则从现在开始计算
                        base_time = current_expire if (current_expire and current_expire > datetime.now()) else datetime.now()
                        new_expire = base_time + timedelta(days=days_to_add)
                        
                        cursor.execute(
                            "UPDATE tenant_quota SET expire_time = %s, billing_type = 'duration', updated_at = %s WHERE tenant_key = %s",
                            (new_expire, now, tenant_key)
                        )
                    else:
                        cursor.execute(
                            "UPDATE tenant_quota SET total_quota = total_quota + %s, billing_type = 'quota', updated_at = %s WHERE tenant_key = %s",
                            (quota_to_add, now, tenant_key)
                        )
                else:
                    if is_subscription:
                        new_expire = datetime.now() + timedelta(days=days_to_add)
                        cursor.execute(
                            "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, expire_time, billing_type, created_at, updated_at) VALUES (%s, %s, %s, %s, 'duration', %s, %s)",
                            (tenant_key, 30, 0, new_expire, now, now)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, billing_type, created_at, updated_at) VALUES (%s, %s, %s, 'quota', %s, %s)",
                            (tenant_key, quota_to_add, 0, now, now)
                        )
                
                # 记录购买历史
                cursor.execute(
                    "INSERT INTO purchase_history (tenant_key, package_name, added_quota, amount, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (tenant_key, package_name, quota_to_add, amount, now)
                )
                
            conn.commit()
            logger.info(f"Recharged {quota_to_add} / Subscription {days_to_add} days for {tenant_key}, package: {package_name}")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to recharge quota for {tenant_key} inside transaction: {e}")
            return False
        finally:
            conn.close()

    def create_payment_order(self, order_id, tenant_key, package_id, pay_type, amount, added_quota, added_days):
        """创建待支付订单"""
        now = datetime.now()
        try:
            self._execute_query(
                "INSERT INTO payment_orders (order_id, tenant_key, package_id, pay_type, amount, added_quota, added_days, status, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (order_id, tenant_key, package_id, pay_type, amount, added_quota, added_days, 'PENDING', now, now), commit=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create payment order {order_id}: {e}")
            return False

    def update_payment_status(self, order_id, status, transaction_id=None):
        """更新订单状态,如果成功则自动充值 (原子防并发双花设计)"""
        now = datetime.now()
        try:
            row = self._execute_query(
                "SELECT tenant_key, status, added_quota, added_days, amount, package_id FROM payment_orders WHERE order_id = %s",
                (order_id,), fetch_one=True
            )
            if not row:
                return False
            
            tenant_key, old_status, added_quota, added_days, amount, package_id = row
            
            # 如果已经是成功状态,则不重复处理
            if old_status == 'SUCCESS':
                return True
            
            if status == 'SUCCESS':
                # 🌟 原子状态翻转：仅当原状态为 PENDING 时才更新为 SUCCESS
                affected_rows = self._execute_query(
                    "UPDATE payment_orders SET status = 'SUCCESS', transaction_id = %s, updated_at = %s WHERE order_id = %s AND status = 'PENDING'",
                    (transaction_id, now, order_id), commit=True
                )
                if affected_rows == 1:
                    # 只有原子更新成功的那个线程，才能触发额度/时长加签逻辑
                    package_name = f"套餐_{package_id}"
                    return self.recharge_quota(tenant_key, package_name, added_quota, amount, package_id, added_days)
                else:
                    # affected_rows == 0 说明已被并发的另一个线程（主动轮询或回调）先一步处理成功并入账了，直接放行
                    return True
            else:
                self._execute_query(
                    "UPDATE payment_orders SET status = %s, updated_at = %s WHERE order_id = %s AND status = 'PENDING'",
                    (status, now, order_id), commit=True
                )
                return True
        except Exception as e:
            logger.error(f"Failed to update payment status for {order_id}: {e}")
            return False

    def get_payment_status(self, order_id):
        """查询订单状态"""
        try:
            row = self._execute_query(
                "SELECT status FROM payment_orders WHERE order_id = %s",
                (order_id,), fetch_one=True
            )
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get payment status for {order_id}: {e}")
            return None

    def bind_app_token_to_tenant(self, app_token, tenant_key):
        """绑定 app_token 到 tenant_key"""
        if not app_token or not tenant_key:
            return False
        now = datetime.now()
        try:
            self._execute_query(
                "INSERT INTO app_token_mapping (app_token, tenant_key, created_at) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE tenant_key = VALUES(tenant_key), created_at = VALUES(created_at)",
                (app_token, tenant_key, now), commit=True
            )
            logger.info(f"Successfully bound app_token {app_token[:10]}... to tenant {tenant_key[:10]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to bind app_token {app_token} to tenant {tenant_key}: {e}")
            return False

    def get_personal_base_token(self, tenant_key):
        """获取租户特定的授权码"""
        if not tenant_key:
            return None
        try:
            row = self._execute_query(
                "SELECT personal_base_token FROM tenant_quota WHERE tenant_key = %s",
                (tenant_key,), fetch_one=True
            )
            return row[0] if (row and row[0]) else None
        except Exception as e:
            logger.error(f"Failed to get token for tenant {tenant_key}: {e}")
            return None

    def get_token_by_app_token(self, app_token):
        """通过 app_token 间接获取绑定的授权码"""
        if not app_token:
            return None
        try:
            row = self._execute_query(
                "SELECT personal_base_token FROM tenant_quota WHERE tenant_key = "
                "(SELECT tenant_key FROM app_token_mapping WHERE app_token = %s)",
                (app_token,), fetch_one=True
            )
            return row[0] if (row and row[0]) else None
        except Exception as e:
            logger.error(f"Failed to get token by app_token {app_token}: {e}")
            return None

    def set_personal_base_token(self, tenant_key, token):
        """保存租户特定的授权码"""
        if not tenant_key or not token:
            return False
        now = datetime.now()
        try:
            row = self._execute_query(
                "SELECT tenant_key FROM tenant_quota WHERE tenant_key = %s",
                (tenant_key,), fetch_one=True
            )
            if row:
                self._execute_query(
                    "UPDATE tenant_quota SET personal_base_token = %s, updated_at = %s WHERE tenant_key = %s",
                    (token, now, tenant_key), commit=True
                )
            else:
                initial_quota = 30 if self.auto_trial else 0
                self._execute_query(
                    "INSERT INTO tenant_quota (tenant_key, total_quota, used_quota, billing_type, personal_base_token, created_at, updated_at) "
                    "VALUES (%s, %s, 0, 'quota', %s, %s, %s)",
                    (tenant_key, initial_quota, token, now, now), commit=True
                )
            logger.info(f"Successfully saved personal_base_token for tenant {tenant_key[:10]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to set token for tenant {tenant_key}: {e}")
            return False
