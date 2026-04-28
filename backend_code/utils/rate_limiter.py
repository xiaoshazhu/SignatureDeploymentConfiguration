"""
API限流器工具类

实现令牌桶算法,用于控制API请求频率,避免触发飞书API频率限制。
支持多线程环境下的并发控制。
"""

import threading
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class APIRateLimiter:
    """
    API限流器 - 基于令牌桶算法
    
    令牌桶算法原理:
    1. 以固定速率向桶中添加令牌
    2. 每次API调用消耗一个令牌
    3. 如果桶中没有令牌,则等待直到有新令牌
    4. 桶有最大容量,多余的令牌会被丢弃
    
    Args:
        max_calls_per_second: 每秒最大请求数(QPS)
        burst_size: 突发容量,允许短时间内的突发请求数
    """
    
    def __init__(self, max_calls_per_second=5, burst_size=10):
        """
        初始化限流器
        
        Args:
            max_calls_per_second: 每秒最大请求数,默认5
            burst_size: 突发容量,默认10
        """
        self.max_calls_per_second = max_calls_per_second
        self.burst_size = burst_size
        
        # 当前令牌数量
        self.tokens = burst_size
        
        # 上次添加令牌的时间
        self.last_update = time.time()
        
        # 线程锁,保证线程安全
        self.lock = threading.Lock()
        
        logger.info(f"初始化API限流器: QPS={max_calls_per_second}, 突发容量={burst_size}")
    
    def _add_tokens(self):
        """
        根据时间流逝添加令牌
        
        私有方法,在获取令牌前调用
        """
        now = time.time()
        elapsed = now - self.last_update
        
        # 计算应该添加的令牌数
        new_tokens = elapsed * self.max_calls_per_second
        
        # 更新令牌数,不超过最大容量
        self.tokens = min(self.burst_size, self.tokens + new_tokens)
        
        # 更新时间戳
        self.last_update = now
    
    def acquire(self, timeout=None):
        """
        获取一个令牌,如果没有令牌则等待
        
        Args:
            timeout: 最大等待时间(秒),None表示无限等待
            
        Returns:
            bool: 是否成功获取令牌
            
        Raises:
            TimeoutError: 如果在timeout时间内未获取到令牌
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                # 添加新令牌
                self._add_tokens()
                
                # 如果有令牌,消耗一个并返回
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
                
                # 计算需要等待的时间
                wait_time = (1 - self.tokens) / self.max_calls_per_second
            
            # 检查是否超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(f"限流器等待超时: {timeout}秒")
                
                # 调整等待时间,不超过剩余时间
                wait_time = min(wait_time, timeout - elapsed)
            
            # 等待一段时间后重试
            time.sleep(wait_time)
    
    def __call__(self, func):
        """
        装饰器用法,自动为函数添加限流控制
        
        使用示例:
            @rate_limiter
            def api_call():
                pass
        
        Args:
            func: 要装饰的函数
            
        Returns:
            装饰后的函数
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取令牌
            self.acquire()
            
            # 执行原函数
            return func(*args, **kwargs)
        
        return wrapper


def retry_on_rate_limit(max_retries=3, initial_delay=1, backoff_factor=2, max_delay=10):
    """
    自动重试装饰器 - 针对API频率限制错误
    
    使用指数退避策略:
    - 第1次重试: 等待 initial_delay 秒
    - 第2次重试: 等待 initial_delay * backoff_factor 秒
    - 第3次重试: 等待 initial_delay * backoff_factor^2 秒
    - 等待时间不超过 max_delay
    
    Args:
        max_retries: 最大重试次数,默认3次
        initial_delay: 初始等待时间(秒),默认1秒
        backoff_factor: 退避因子,默认2(每次翻倍)
        max_delay: 最大等待时间(秒),默认10秒
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    # 执行原函数
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否是频率限制错误
                    error_msg = str(e).lower()
                    is_rate_limit_error = (
                        'frequency limit' in error_msg or
                        '99991400' in error_msg or
                        'rate limit' in error_msg
                    )
                    
                    # 如果不是频率限制错误,直接抛出
                    if not is_rate_limit_error:
                        raise
                    
                    # 如果已经是最后一次尝试,抛出异常
                    if attempt >= max_retries:
                        logger.error(f"达到最大重试次数({max_retries}),放弃重试")
                        raise
                    
                    # 计算等待时间(指数退避)
                    delay = min(initial_delay * (backoff_factor ** attempt), max_delay)
                    
                    logger.warning(
                        f"检测到频率限制错误,第{attempt + 1}次重试,"
                        f"等待{delay:.2f}秒... 错误: {e}"
                    )
                    
                    # 等待后重试
                    time.sleep(delay)
            
            # 理论上不会到这里,但为了安全还是抛出最后的异常
            raise last_exception
        
        return wrapper
    return decorator


# 创建全局限流器实例
# 优化: 极致稳定性模式 (3 QPS), 适用于 2000+ 条大批量生成, 防止触发持续限流
feishu_api_limiter = APIRateLimiter(max_calls_per_second=3, burst_size=5)


if __name__ == "__main__":
    # 测试代码
    import concurrent.futures
    
    logging.basicConfig(level=logging.INFO)
    
    # 测试限流器
    test_limiter = APIRateLimiter(max_calls_per_second=2, burst_size=5)
    
    @test_limiter
    def test_api_call(call_id):
        """模拟API调用"""
        print(f"[{time.time():.2f}] 执行API调用 #{call_id}")
        return call_id
    
    # 并发测试
    print("开始并发测试(10个线程,每秒限制2个请求)...")
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(test_api_call, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    elapsed = time.time() - start
    print(f"\n完成10次调用,耗时: {elapsed:.2f}秒")
    print(f"预期耗时: ~5秒 (10次调用 / 2次每秒)")
    
    # 测试重试装饰器
    print("\n\n测试重试装饰器...")
    
    @retry_on_rate_limit(max_retries=3, initial_delay=0.5)
    def test_retry_api():
        """模拟会失败的API调用"""
        import random
        if random.random() < 0.7:  # 70%概率失败
            raise Exception("request trigger frequency limit")
        return "成功"
    
    try:
        result = test_retry_api()
        print(f"API调用结果: {result}")
    except Exception as e:
        print(f"API调用最终失败: {e}")
