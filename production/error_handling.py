"""
集計エラーハンドリングとリトライ機能
"""

import logging
import time
import traceback
from functools import wraps
from typing import Callable, Any, Optional, Dict
from datetime import datetime
from django.db import transaction, OperationalError, IntegrityError
from django.core.cache import cache
from .exceptions import (
    AggregationError, DataInconsistencyError, AggregationTimeoutError,
    DatabaseConnectionError, ValidationError, ConcurrencyError,
    RetryableError, NonRetryableError
)

logger = logging.getLogger(__name__)


class ErrorHandler:
    """集計エラーハンドリングクラス"""
    
    def __init__(self):
        self.error_stats = {}
        self.logger = logger
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """エラーを処理し、適切な対応を決定"""
        context = context or {}
        
        # エラー情報を記録
        error_info = self._create_error_info(error, context)
        self._log_error(error_info)
        self._update_error_stats(error_info)
        
        # エラー種別に応じた処理
        if isinstance(error, RetryableError):
            return self._handle_retryable_error(error, error_info)
        elif isinstance(error, NonRetryableError):
            return self._handle_non_retryable_error(error, error_info)
        elif isinstance(error, (OperationalError, DatabaseConnectionError)):
            return self._handle_database_error(error, error_info)
        elif isinstance(error, IntegrityError):
            return self._handle_integrity_error(error, error_info)
        else:
            return self._handle_unknown_error(error, error_info)
    
    def _create_error_info(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """エラー情報を作成"""
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'error_type': error.__class__.__name__,
            'message': str(error),
            'context': context,
            'traceback': traceback.format_exc()
        }
        
        # カスタム例外の場合は詳細情報を追加
        if isinstance(error, AggregationError):
            error_info.update(error.to_dict())
        
        return error_info
    
    def _log_error(self, error_info: Dict[str, Any]):
        """エラーをログに記録"""
        error_type = error_info['error_type']
        message = error_info['message']
        context = error_info.get('context', {})
        
        log_message = f"集計エラー [{error_type}]: {message}"
        
        if context:
            log_message += f" | コンテキスト: {context}"
        
        # エラーレベルに応じてログレベルを調整
        if error_type in ['ValidationError', 'DataInconsistencyError']:
            self.logger.warning(log_message)
        elif error_type in ['RetryableError', 'DatabaseConnectionError']:
            self.logger.error(log_message)
        else:
            self.logger.critical(log_message)
        
        # 詳細なトレースバックをデバッグレベルで記録
        self.logger.debug(f"エラートレースバック: {error_info['traceback']}")
    
    def _update_error_stats(self, error_info: Dict[str, Any]):
        """エラー統計を更新"""
        error_type = error_info['error_type']
        
        if error_type not in self.error_stats:
            self.error_stats[error_type] = {
                'count': 0,
                'first_occurrence': error_info['timestamp'],
                'last_occurrence': error_info['timestamp']
            }
        
        self.error_stats[error_type]['count'] += 1
        self.error_stats[error_type]['last_occurrence'] = error_info['timestamp']
        
        # キャッシュにも保存（監視用）
        cache_key = f"aggregation_error_stats_{error_type}"
        cache.set(cache_key, self.error_stats[error_type], 3600)  # 1時間
    
    def _handle_retryable_error(self, error: RetryableError, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """リトライ可能エラーの処理"""
        if error.can_retry():
            return {
                'action': 'retry',
                'delay': min(2 ** error.retry_count, 60),  # 指数バックオフ（最大60秒）
                'error_info': error_info
            }
        else:
            return {
                'action': 'fail',
                'reason': 'max_retries_exceeded',
                'error_info': error_info
            }
    
    def _handle_non_retryable_error(self, error: NonRetryableError, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """リトライ不可能エラーの処理"""
        return {
            'action': 'fail',
            'reason': 'non_retryable',
            'error_info': error_info
        }
    
    def _handle_database_error(self, error: Exception, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """データベースエラーの処理"""
        return {
            'action': 'retry',
            'delay': 5,  # 5秒後にリトライ
            'max_retries': 3,
            'error_info': error_info
        }
    
    def _handle_integrity_error(self, error: IntegrityError, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """整合性エラーの処理"""
        # 重複キー制約違反の場合は無視
        if 'duplicate key' in str(error).lower() or 'unique constraint' in str(error).lower():
            return {
                'action': 'ignore',
                'reason': 'duplicate_key',
                'error_info': error_info
            }
        else:
            return {
                'action': 'fail',
                'reason': 'integrity_violation',
                'error_info': error_info
            }
    
    def _handle_unknown_error(self, error: Exception, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """未知のエラーの処理"""
        return {
            'action': 'retry',
            'delay': 10,
            'max_retries': 1,
            'error_info': error_info
        }
    
    def get_error_stats(self) -> Dict[str, Any]:
        """エラー統計を取得"""
        return self.error_stats.copy()


def with_error_handling(max_retries: int = 3, base_delay: float = 1.0):
    """エラーハンドリングデコレータ"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            error_handler = ErrorHandler()
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except Exception as e:
                    last_error = e
                    
                    # コンテキスト情報を作成
                    context = {
                        'function': func.__name__,
                        'attempt': attempt + 1,
                        'max_retries': max_retries,
                        'args': str(args)[:200],  # 長すぎる場合は切り詰め
                        'kwargs': str(kwargs)[:200]
                    }
                    
                    # エラーハンドリング
                    result = error_handler.handle_error(e, context)
                    
                    if result['action'] == 'ignore':
                        logger.info(f"エラーを無視: {result['reason']}")
                        return None
                    elif result['action'] == 'fail':
                        logger.error(f"処理失敗: {result['reason']}")
                        break
                    elif result['action'] == 'retry' and attempt < max_retries:
                        delay = result.get('delay', base_delay * (2 ** attempt))
                        logger.info(f"リトライ {attempt + 1}/{max_retries} を {delay}秒後に実行")
                        time.sleep(delay)
                        continue
                    else:
                        break
            
            # 最終的に失敗した場合
            if isinstance(last_error, AggregationError):
                raise last_error
            else:
                raise AggregationError(
                    f"処理が失敗しました: {str(last_error)}",
                    error_code='PROCESSING_FAILED'
                )
        
        return wrapper
    return decorator


def with_timeout(timeout_seconds: int):
    """タイムアウトデコレータ"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import signal
            
            def timeout_handler(signum, frame):
                raise AggregationTimeoutError(
                    f"処理がタイムアウトしました: {timeout_seconds}秒",
                    timeout_seconds=timeout_seconds,
                    operation=func.__name__
                )
            
            # タイムアウト設定
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            
            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # タイムアウトをクリア
                return result
            finally:
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    return decorator


def with_transaction_retry(max_retries: int = 3):
    """トランザクションリトライデコレータ"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries + 1):
                try:
                    with transaction.atomic():
                        return func(*args, **kwargs)
                
                except (OperationalError, IntegrityError) as e:
                    if attempt < max_retries:
                        delay = 0.5 * (2 ** attempt)  # 指数バックオフ
                        logger.warning(f"トランザクションリトライ {attempt + 1}/{max_retries}: {delay}秒後")
                        time.sleep(delay)
                        continue
                    else:
                        raise DatabaseConnectionError(
                            f"トランザクション処理が失敗しました: {str(e)}"
                        )
        
        return wrapper
    return decorator


class CircuitBreaker:
    """サーキットブレーカーパターンの実装"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """サーキットブレーカー経由で関数を呼び出し"""
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise AggregationError(
                    "サーキットブレーカーが開いています",
                    error_code='CIRCUIT_BREAKER_OPEN'
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """リセットを試行すべきかどうか"""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """成功時の処理"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """失敗時の処理"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"サーキットブレーカーが開きました: {self.failure_count}回の失敗")


# グローバルサーキットブレーカーインスタンス
aggregation_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)