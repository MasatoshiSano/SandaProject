"""
集計システムの監視とアラート機能
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Avg, Max, Min
from .models import WeeklyResultAggregation, Result, Line
from .exceptions import AggregationError

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """パフォーマンス監視クラス"""
    
    def __init__(self):
        self.metrics = {}
        self.logger = logger
    
    def start_operation(self, operation_name: str) -> str:
        """操作の開始を記録"""
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        self.metrics[operation_id] = {
            'operation': operation_name,
            'start_time': time.time(),
            'status': 'running'
        }
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool = True, error: Exception = None):
        """操作の終了を記録"""
        if operation_id not in self.metrics:
            return
        
        end_time = time.time()
        metric = self.metrics[operation_id]
        
        metric.update({
            'end_time': end_time,
            'duration': end_time - metric['start_time'],
            'status': 'success' if success else 'failed',
            'error': str(error) if error else None
        })
        
        # パフォーマンス統計を更新
        self._update_performance_stats(metric)
        
        # 閾値チェック
        self._check_performance_thresholds(metric)
    
    def _update_performance_stats(self, metric: Dict[str, Any]):
        """パフォーマンス統計を更新"""
        operation = metric['operation']
        duration = metric['duration']
        
        # キャッシュから既存の統計を取得
        stats_key = f"perf_stats_{operation}"
        stats = cache.get(stats_key, {
            'count': 0,
            'total_duration': 0,
            'min_duration': float('inf'),
            'max_duration': 0,
            'success_count': 0,
            'failure_count': 0
        })
        
        # 統計を更新
        stats['count'] += 1
        stats['total_duration'] += duration
        stats['min_duration'] = min(stats['min_duration'], duration)
        stats['max_duration'] = max(stats['max_duration'], duration)
        
        if metric['status'] == 'success':
            stats['success_count'] += 1
        else:
            stats['failure_count'] += 1
        
        # 平均を計算
        stats['avg_duration'] = stats['total_duration'] / stats['count']
        stats['success_rate'] = stats['success_count'] / stats['count'] * 100
        
        # キャッシュに保存（1時間）
        cache.set(stats_key, stats, 3600)
    
    def _check_performance_thresholds(self, metric: Dict[str, Any]):
        """パフォーマンス閾値をチェック"""
        operation = metric['operation']
        duration = metric['duration']
        
        # 操作別の閾値設定
        thresholds = {
            'aggregate_single_date': 5.0,  # 5秒
            'aggregate_date_range': 30.0,  # 30秒
            'incremental_update': 1.0,     # 1秒
            'validate_aggregation': 10.0,  # 10秒
            'get_weekly_data': 0.1,        # 100ms
            'get_performance_metrics': 0.1  # 100ms
        }
        
        threshold = thresholds.get(operation, 10.0)  # デフォルト10秒
        
        if duration > threshold:
            self.logger.warning(
                f"パフォーマンス閾値超過: {operation} が {duration:.2f}秒 "
                f"(閾値: {threshold}秒)"
            )
            
            # アラートを送信
            AlertManager().send_performance_alert(operation, duration, threshold)
    
    def get_performance_stats(self, operation: str = None) -> Dict[str, Any]:
        """パフォーマンス統計を取得"""
        if operation:
            stats_key = f"perf_stats_{operation}"
            return cache.get(stats_key, {})
        else:
            # すべての操作の統計を取得
            all_stats = {}
            operations = [
                'aggregate_single_date', 'aggregate_date_range',
                'incremental_update', 'validate_aggregation',
                'get_weekly_data', 'get_performance_metrics'
            ]
            
            for op in operations:
                stats_key = f"perf_stats_{op}"
                stats = cache.get(stats_key)
                if stats:
                    all_stats[op] = stats
            
            return all_stats


class HealthChecker:
    """システムヘルスチェッククラス"""
    
    def __init__(self):
        self.logger = logger
    
    def check_system_health(self) -> Dict[str, Any]:
        """システム全体のヘルスチェック"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        # 各種チェックを実行
        checks = [
            ('database', self._check_database_health),
            ('aggregation_data', self._check_aggregation_data_health),
            ('performance', self._check_performance_health),
            ('memory', self._check_memory_health),
            ('cache', self._check_cache_health)
        ]
        
        for check_name, check_func in checks:
            try:
                result = check_func()
                health_status['checks'][check_name] = result
                
                if result['status'] != 'healthy':
                    health_status['overall_status'] = 'degraded'
                    
            except Exception as e:
                health_status['checks'][check_name] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_status['overall_status'] = 'unhealthy'
        
        return health_status
    
    def _check_database_health(self) -> Dict[str, Any]:
        """データベースヘルスチェック"""
        try:
            # 基本的な接続テスト
            result_count = Result.objects.count()
            aggregation_count = WeeklyResultAggregation.objects.count()
            
            # 最新データの確認
            latest_result = Result.objects.order_by('-timestamp').first()
            latest_aggregation = WeeklyResultAggregation.objects.order_by('-date').first()
            
            # データの新しさをチェック
            now = datetime.now()
            data_freshness = 'good'
            
            if latest_result:
                result_age = now - latest_result.timestamp.replace(tzinfo=None)
                if result_age > timedelta(hours=24):
                    data_freshness = 'stale'
            
            return {
                'status': 'healthy',
                'result_count': result_count,
                'aggregation_count': aggregation_count,
                'latest_result': latest_result.timestamp.isoformat() if latest_result else None,
                'latest_aggregation': latest_aggregation.date.isoformat() if latest_aggregation else None,
                'data_freshness': data_freshness
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_aggregation_data_health(self) -> Dict[str, Any]:
        """集計データのヘルスチェック"""
        try:
            # ライン別の集計データ統計
            line_stats = WeeklyResultAggregation.objects.values('line').annotate(
                count=Count('id'),
                latest_date=Max('date'),
                earliest_date=Min('date')
            )
            
            # データの整合性チェック
            inconsistencies = []
            for stat in line_stats:
                line_name = stat['line']
                
                # 最近7日間のデータをチェック
                recent_date = datetime.now().date() - timedelta(days=7)
                recent_aggregations = WeeklyResultAggregation.objects.filter(
                    line=line_name,
                    date__gte=recent_date
                ).count()
                
                if recent_aggregations == 0:
                    inconsistencies.append(f"ライン {line_name} の最近のデータがありません")
            
            status = 'healthy' if not inconsistencies else 'degraded'
            
            return {
                'status': status,
                'line_count': len(line_stats),
                'total_aggregations': sum(stat['count'] for stat in line_stats),
                'inconsistencies': inconsistencies
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_performance_health(self) -> Dict[str, Any]:
        """パフォーマンスヘルスチェック"""
        try:
            monitor = PerformanceMonitor()
            stats = monitor.get_performance_stats()
            
            # パフォーマンス問題をチェック
            issues = []
            for operation, stat in stats.items():
                if stat.get('success_rate', 100) < 95:
                    issues.append(f"{operation} の成功率が低い: {stat['success_rate']:.1f}%")
                
                if stat.get('avg_duration', 0) > 5:
                    issues.append(f"{operation} の平均実行時間が長い: {stat['avg_duration']:.2f}秒")
            
            status = 'healthy' if not issues else 'degraded'
            
            return {
                'status': status,
                'operations_monitored': len(stats),
                'issues': issues
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_memory_health(self) -> Dict[str, Any]:
        """メモリヘルスチェック"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # メモリ使用量の閾値チェック
            memory_threshold = 1024  # 1GB
            status = 'healthy' if memory_mb < memory_threshold else 'degraded'
            
            return {
                'status': status,
                'memory_usage_mb': round(memory_mb, 2),
                'memory_threshold_mb': memory_threshold
            }
            
        except ImportError:
            # psutilが利用できない場合
            return {
                'status': 'unknown',
                'message': 'psutil not available'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_cache_health(self) -> Dict[str, Any]:
        """キャッシュヘルスチェック"""
        try:
            # キャッシュの読み書きテスト
            test_key = 'health_check_test'
            test_value = datetime.now().isoformat()
            
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            
            if retrieved_value == test_value:
                cache.delete(test_key)
                return {
                    'status': 'healthy',
                    'cache_type': cache.__class__.__name__
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': 'Cache read/write test failed'
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }


class AlertManager:
    """アラート管理クラス"""
    
    def __init__(self):
        self.logger = logger
        self.alert_cooldown = 300  # 5分間のクールダウン
    
    def send_performance_alert(self, operation: str, duration: float, threshold: float):
        """パフォーマンスアラートを送信"""
        alert_key = f"perf_alert_{operation}"
        
        # クールダウンチェック
        if cache.get(alert_key):
            return
        
        message = (
            f"パフォーマンス警告\n"
            f"操作: {operation}\n"
            f"実行時間: {duration:.2f}秒\n"
            f"閾値: {threshold}秒\n"
            f"時刻: {datetime.now().isoformat()}"
        )
        
        self._send_alert("パフォーマンス警告", message)
        
        # クールダウンを設定
        cache.set(alert_key, True, self.alert_cooldown)
    
    def send_error_alert(self, error: AggregationError, context: Dict[str, Any] = None):
        """エラーアラートを送信"""
        alert_key = f"error_alert_{error.error_code}"
        
        # クールダウンチェック
        if cache.get(alert_key):
            return
        
        message = (
            f"集計エラー発生\n"
            f"エラータイプ: {error.__class__.__name__}\n"
            f"エラーコード: {error.error_code}\n"
            f"メッセージ: {error.message}\n"
            f"詳細: {error.details}\n"
            f"時刻: {datetime.now().isoformat()}"
        )
        
        if context:
            message += f"\nコンテキスト: {context}"
        
        self._send_alert("集計エラー発生", message)
        
        # クールダウンを設定
        cache.set(alert_key, True, self.alert_cooldown)
    
    def send_health_alert(self, health_status: Dict[str, Any]):
        """ヘルスチェックアラートを送信"""
        if health_status['overall_status'] == 'healthy':
            return
        
        alert_key = "health_alert"
        
        # クールダウンチェック
        if cache.get(alert_key):
            return
        
        unhealthy_checks = [
            name for name, check in health_status['checks'].items()
            if check.get('status') != 'healthy'
        ]
        
        message = (
            f"システムヘルス警告\n"
            f"全体ステータス: {health_status['overall_status']}\n"
            f"問題のあるチェック: {', '.join(unhealthy_checks)}\n"
            f"時刻: {health_status['timestamp']}"
        )
        
        self._send_alert("システムヘルス警告", message)
        
        # クールダウンを設定
        cache.set(alert_key, True, self.alert_cooldown)
    
    def _send_alert(self, subject: str, message: str):
        """アラートを送信（メール、ログ等）"""
        # ログに記録
        self.logger.critical(f"ALERT: {subject} - {message}")
        
        # メール送信（設定されている場合）
        if hasattr(settings, 'ALERT_EMAIL_RECIPIENTS') and settings.ALERT_EMAIL_RECIPIENTS:
            try:
                send_mail(
                    subject=f"[週別分析システム] {subject}",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=settings.ALERT_EMAIL_RECIPIENTS,
                    fail_silently=False
                )
                self.logger.info(f"アラートメールを送信: {subject}")
            except Exception as e:
                self.logger.error(f"アラートメール送信エラー: {e}")
        
        # WebSocket通知（管理者向け）
        try:
            from .models import send_aggregation_status_notification
            send_aggregation_status_notification('alert', {
                'subject': subject,
                'message': message,
                'severity': 'critical'
            })
        except Exception as e:
            self.logger.error(f"WebSocketアラート送信エラー: {e}")


# グローバルインスタンス
performance_monitor = PerformanceMonitor()
health_checker = HealthChecker()
alert_manager = AlertManager()