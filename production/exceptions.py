"""
週別分析パフォーマンス改善のためのカスタム例外クラス
"""

class AggregationError(Exception):
    """集計処理の基本例外クラス"""
    
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.message = message
    
    def to_dict(self):
        """例外情報を辞書形式で返す"""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


class DataInconsistencyError(AggregationError):
    """データ整合性エラー"""
    
    def __init__(self, message, line_name=None, date=None, expected=None, actual=None):
        super().__init__(message, error_code='DATA_INCONSISTENCY')
        self.details.update({
            'line_name': line_name,
            'date': date.isoformat() if date else None,
            'expected': expected,
            'actual': actual
        })


class AggregationTimeoutError(AggregationError):
    """集計処理タイムアウトエラー"""
    
    def __init__(self, message, timeout_seconds=None, operation=None):
        super().__init__(message, error_code='AGGREGATION_TIMEOUT')
        self.details.update({
            'timeout_seconds': timeout_seconds,
            'operation': operation
        })


class DatabaseConnectionError(AggregationError):
    """データベース接続エラー"""
    
    def __init__(self, message, connection_info=None):
        super().__init__(message, error_code='DATABASE_CONNECTION')
        self.details.update({
            'connection_info': connection_info
        })


class ValidationError(AggregationError):
    """データ検証エラー"""
    
    def __init__(self, message, field_name=None, invalid_value=None, validation_rule=None):
        super().__init__(message, error_code='VALIDATION_ERROR')
        self.details.update({
            'field_name': field_name,
            'invalid_value': invalid_value,
            'validation_rule': validation_rule
        })


class ConcurrencyError(AggregationError):
    """並行処理エラー"""
    
    def __init__(self, message, resource=None, conflict_type=None):
        super().__init__(message, error_code='CONCURRENCY_ERROR')
        self.details.update({
            'resource': resource,
            'conflict_type': conflict_type
        })


class MemoryError(AggregationError):
    """メモリ不足エラー"""
    
    def __init__(self, message, memory_usage=None, memory_limit=None):
        super().__init__(message, error_code='MEMORY_ERROR')
        self.details.update({
            'memory_usage': memory_usage,
            'memory_limit': memory_limit
        })


class ConfigurationError(AggregationError):
    """設定エラー"""
    
    def __init__(self, message, config_key=None, config_value=None):
        super().__init__(message, error_code='CONFIGURATION_ERROR')
        self.details.update({
            'config_key': config_key,
            'config_value': config_value
        })


class RetryableError(AggregationError):
    """リトライ可能エラー"""
    
    def __init__(self, message, retry_count=0, max_retries=3):
        super().__init__(message, error_code='RETRYABLE_ERROR')
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.details.update({
            'retry_count': retry_count,
            'max_retries': max_retries
        })
    
    def can_retry(self):
        """リトライ可能かどうかを判定"""
        return self.retry_count < self.max_retries


class NonRetryableError(AggregationError):
    """リトライ不可能エラー"""
    
    def __init__(self, message, reason=None):
        super().__init__(message, error_code='NON_RETRYABLE_ERROR')
        self.details.update({
            'reason': reason
        })