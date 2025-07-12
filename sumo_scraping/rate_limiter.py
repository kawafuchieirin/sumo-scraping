"""
レート制限とリクエスト管理モジュール
"""

import asyncio
import random
import time
from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """レート制限設定"""
    min_delay: float = 3.0  # 最小待機時間（秒）
    max_delay: float = 8.0  # 最大待機時間（秒）
    page_delay: float = 5.0  # ページ間の待機時間（秒）
    station_delay: float = 10.0  # 駅間の待機時間（秒）
    max_retries: int = 3  # 最大リトライ回数
    retry_delay: float = 5.0  # リトライ時の待機時間（秒）
    concurrent_limit: int = 1  # 同時実行数制限
    
class RateLimiter:
    """レート制限管理クラス"""
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.last_request_time = 0.0
        self.request_count = 0
        self.session_start_time = time.time()
        self._semaphore = asyncio.Semaphore(self.config.concurrent_limit)
        
    async def wait_for_request(self, request_type: str = "default"):
        """リクエスト前の待機処理"""
        async with self._semaphore:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            
            # リクエストタイプに応じた待機時間を決定
            if request_type == "page":
                required_delay = self.config.page_delay
            elif request_type == "station":
                required_delay = self.config.station_delay
            else:
                # ランダムな待機時間（人間らしいアクセスパターン）
                required_delay = random.uniform(
                    self.config.min_delay, 
                    self.config.max_delay
                )
            
            if elapsed < required_delay:
                wait_time = required_delay - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.1f}s for {request_type}")
                await asyncio.sleep(wait_time)
            
            self.last_request_time = time.time()
            self.request_count += 1
            
            # セッション統計をログ出力
            if self.request_count % 10 == 0:
                session_duration = self.last_request_time - self.session_start_time
                avg_interval = session_duration / self.request_count
                logger.info(f"Rate limiter stats: {self.request_count} requests, "
                          f"avg interval: {avg_interval:.1f}s")

class RetryManager:
    """リトライ管理クラス"""
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
    
    async def execute_with_retry(self, func, *args, **kwargs):
        """指数バックオフによるリトライ実行"""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == self.config.max_retries:
                    logger.error(f"Max retries ({self.config.max_retries}) exceeded: {e}")
                    raise e
                
                # 指数バックオフ
                wait_time = self.config.retry_delay * (2 ** attempt)
                jitter = random.uniform(0.5, 1.5)  # ジッターを追加
                actual_wait = wait_time * jitter
                
                logger.warning(f"Attempt {attempt + 1} failed: {e}. "
                             f"Retrying in {actual_wait:.1f}s...")
                await asyncio.sleep(actual_wait)
        
        raise last_exception

class UserAgentRotator:
    """User-Agent ローテーション管理"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        self.current_index = 0
    
    def get_random_user_agent(self) -> str:
        """ランダムなUser-Agentを取得"""
        return random.choice(self.user_agents)
    
    def get_next_user_agent(self) -> str:
        """順番にUser-Agentを取得"""
        user_agent = self.user_agents[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.user_agents)
        return user_agent

class RequestMonitor:
    """リクエスト監視とロギング"""
    
    def __init__(self):
        self.start_time = time.time()
        self.request_times: List[float] = []
        self.error_count = 0
        self.success_count = 0
    
    def record_request(self, success: bool = True, response_time: Optional[float] = None):
        """リクエスト結果を記録"""
        current_time = time.time()
        self.request_times.append(current_time)
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        # 古いレコードを削除（直近1時間のみ保持）
        cutoff_time = current_time - 3600
        self.request_times = [t for t in self.request_times if t > cutoff_time]
    
    def get_request_rate(self, window_seconds: int = 300) -> float:
        """指定時間窓でのリクエストレートを取得"""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        recent_requests = [t for t in self.request_times if t > cutoff_time]
        return len(recent_requests) / window_seconds
    
    def get_stats(self) -> dict:
        """統計情報を取得"""
        current_time = time.time()
        session_duration = current_time - self.start_time
        total_requests = self.success_count + self.error_count
        
        return {
            'session_duration': session_duration,
            'total_requests': total_requests,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': self.success_count / total_requests if total_requests > 0 else 0,
            'avg_request_rate': total_requests / session_duration if session_duration > 0 else 0,
            'recent_request_rate': self.get_request_rate(300)  # 直近5分間
        }
    
    def log_stats(self):
        """統計情報をログ出力"""
        stats = self.get_stats()
        logger.info(f"Request stats: {stats['total_requests']} total, "
                   f"{stats['success_rate']:.1%} success rate, "
                   f"{stats['recent_request_rate']:.2f} req/s (recent)")

class PoliteRequestManager:
    """礼儀正しいリクエスト管理"""
    
    def __init__(self, config: RateLimitConfig = None):
        self.rate_limiter = RateLimiter(config)
        self.retry_manager = RetryManager(config)
        self.user_agent_rotator = UserAgentRotator()
        self.monitor = RequestMonitor()
        
    async def make_request(self, func, request_type: str = "default", *args, **kwargs):
        """礼儀正しいリクエスト実行"""
        # レート制限
        await self.rate_limiter.wait_for_request(request_type)
        
        # リトライ付き実行
        start_time = time.time()
        try:
            result = await self.retry_manager.execute_with_retry(func, *args, **kwargs)
            response_time = time.time() - start_time
            self.monitor.record_request(True, response_time)
            return result
        except Exception as e:
            response_time = time.time() - start_time
            self.monitor.record_request(False, response_time)
            raise e
    
    def get_current_user_agent(self) -> str:
        """現在のUser-Agentを取得"""
        return self.user_agent_rotator.get_random_user_agent()
    
    def log_session_stats(self):
        """セッション統計をログ出力"""
        self.monitor.log_stats()