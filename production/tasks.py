"""
Celeryタスク定義

バックグラウンドで実行される非同期タスクを定義する。
"""

try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    # Celeryが利用できない場合のダミーデコレータ
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    CELERY_AVAILABLE = False

from django.utils import timezone
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def calculate_forecast_task(self, line_id: int, target_date_str: str):
    """
    終了予測計算タスク
    
    Args:
        line_id: ライン ID
        target_date_str: 対象日付 (YYYY-MM-DD形式)
    """
    try:
        from production.services.forecast_service import OptimizedForecastService
        
        target_date = timezone.datetime.strptime(target_date_str, '%Y-%m-%d').date()
        
        forecast_service = OptimizedForecastService()
        forecast_time_str = forecast_service.get_forecast_time(line_id, target_date)
        
        # OptimizedForecastServiceは時刻文字列を返すため、結果を変換
        if forecast_time_str not in ['計画なし', '完了済み', '計算エラー']:
            logger.info(f'予測計算タスク完了: line={line_id}, date={target_date_str}')
            return {
                'success': True,
                'line_id': line_id,
                'target_date': target_date_str,
                'completion_time': forecast_time_str,
                'confidence': 85  # 最適化版のデフォルト信頼度
            }
        else:
            logger.error(f'予測計算タスク失敗: line={line_id}, date={target_date_str}, error={result.get("error")}')
            return {
                'success': False,
                'line_id': line_id,
                'target_date': target_date_str,
                'error': result.get('error')
            }
            
    except Exception as e:
        logger.error(f'予測計算タスク例外: line={line_id}, date={target_date_str}, error={str(e)}')
        
        # リトライ処理
        if self.request.retries < self.max_retries:
            logger.info(f'予測計算タスクをリトライ: {self.request.retries + 1}/{self.max_retries}')
            raise self.retry(countdown=60 * (self.request.retries + 1))  # 指数バックオフ
        
        return {
            'success': False,
            'line_id': line_id,
            'target_date': target_date_str,
            'error': str(e),
            'retries_exhausted': True
        }


@shared_task
def update_optimized_forecasts_task():
    """
    最適化された予測更新タスク（15分間隔実行）
    """
    try:
        from production.models import Line
        from production.services.forecast_service import OptimizedForecastService
        
        # 有効なラインを取得
        active_lines = Line.objects.filter(is_active=True)
        
        if not active_lines.exists():
            logger.info('有効なラインがありません')
            return {'success': True, 'message': '対象ラインなし'}
        
        today = timezone.now().date()
        optimized_service = OptimizedForecastService()
        
        updated_count = 0
        error_count = 0
        
        for line in active_lines:
            try:
                # 今日の予測を更新（キャッシュを強制更新）
                optimized_service.clear_cache(line.id, today)
                forecast_time = optimized_service.get_forecast_time(line.id, today)
                
                if forecast_time not in ['計算エラー', '計画なし']:
                    updated_count += 1
                    logger.debug(f'予測更新完了: line={line.id}, time={forecast_time}')
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                logger.error(f'ライン{line.id}の予測更新エラー: {e}')
        
        logger.info(f'予測更新タスク完了: 成功={updated_count}, エラー={error_count}')
        
        return {
            'success': True,
            'updated_count': updated_count,
            'error_count': error_count,
            'total_lines': len(active_lines)
        }
        
    except Exception as e:
        logger.error(f'予測更新タスク例外: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def clear_forecast_cache_task(line_id: int = None, target_date_str: str = None):
    """
    予測キャッシュクリアタスク
    
    Args:
        line_id: ライン ID（Noneの場合は全ライン）
        target_date_str: 対象日付（Noneの場合は今日）
    """
    try:
        from production.services.forecast_service import OptimizedForecastService
        
        forecast_service = OptimizedForecastService()
        
        if target_date_str:
            target_date = timezone.datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = timezone.now().date()
        
        if line_id:
            forecast_service.clear_forecast_cache(line_id, target_date)
            logger.info(f'予測キャッシュクリア完了: line={line_id}, date={target_date}')
        else:
            from production.models import Line
            lines = Line.objects.filter(is_active=True)
            
            for line in lines:
                forecast_service.clear_forecast_cache(line.id, target_date)
            
            logger.info(f'全ライン予測キャッシュクリア完了: {len(lines)}ライン, date={target_date}')
        
        return {
            'success': True,
            'line_id': line_id,
            'target_date': target_date_str or target_date.strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        logger.error(f'予測キャッシュクリアタスク例外: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def update_dashboard_cache_task(line_id: int, date_str: str):
    """
    ダッシュボードキャッシュ更新タスク
    
    Args:
        line_id: ライン ID
        date_str: 対象日付 (YYYY-MM-DD形式)
    """
    try:
        from production.utils import get_dashboard_data, clear_dashboard_cache
        
        # 既存キャッシュをクリア
        clear_dashboard_cache(line_id, date_str)
        
        # 新しいデータを取得してキャッシュに保存
        dashboard_data = get_dashboard_data(line_id, date_str)
        
        logger.info(f'ダッシュボードキャッシュ更新完了: line={line_id}, date={date_str}')
        
        return {
            'success': True,
            'line_id': line_id,
            'date_str': date_str,
            'data_keys': list(dashboard_data.keys()) if dashboard_data else []
        }
        
    except Exception as e:
        logger.error(f'ダッシュボードキャッシュ更新タスク例外: {str(e)}')
        return {
            'success': False,
            'line_id': line_id,
            'date_str': date_str,
            'error': str(e)
        }
@shared_ta
sk
def clear_old_cache_task():
    """
    古いキャッシュをクリアするタスク（1時間間隔実行）
    """
    try:
        from django.core.cache import cache
        from production.models import Line
        
        # 昨日以前のキャッシュをクリア
        yesterday = (timezone.now().date() - timedelta(days=1)).strftime('%Y%m%d')
        
        active_lines = Line.objects.filter(is_active=True)
        cleared_keys = []
        
        for line in active_lines:
            # 古い日付のキャッシュキーを生成
            old_cache_keys = [
                f"optimized_forecast_{line.id}_{yesterday}",
                f"part_actuals_opt_{line.id}_{yesterday}",
                f"plans_{line.id}_{yesterday}",
                f"dashboard_data_{line.id}_{yesterday}",
                f"hourly_data_{line.id}_{yesterday}",
            ]
            
            cleared_keys.extend(old_cache_keys)
        
        # 一括でキャッシュクリア
        cache.delete_many(cleared_keys)
        
        logger.info(f'古いキャッシュクリア完了: {len(cleared_keys)}件')
        
        return {
            'success': True,
            'cleared_keys_count': len(cleared_keys),
            'target_date': yesterday
        }
        
    except Exception as e:
        logger.error(f'古いキャッシュクリアタスク例外: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def warm_up_cache_task():
    """
    キャッシュウォームアップタスク（毎朝7:30実行）
    """
    try:
        from production.models import Line
        from production.utils import get_dashboard_data
        from production.services.forecast_service import OptimizedForecastService
        
        today = timezone.now().date()
        today_str = today.strftime('%Y-%m-%d')
        
        active_lines = Line.objects.filter(is_active=True)
        warmed_up_count = 0
        
        optimized_service = OptimizedForecastService()
        
        for line in active_lines:
            try:
                # ダッシュボードデータをウォームアップ
                dashboard_data = get_dashboard_data(line.id, today_str)
                
                # 予測データをウォームアップ
                forecast_time = optimized_service.get_forecast_time(line.id, today)
                
                warmed_up_count += 1
                logger.debug(f'キャッシュウォームアップ完了: line={line.id}')
                
            except Exception as e:
                logger.error(f'ライン{line.id}のキャッシュウォームアップエラー: {e}')
        
        logger.info(f'キャッシュウォームアップ完了: {warmed_up_count}ライン')
        
        return {
            'success': True,
            'warmed_up_count': warmed_up_count,
            'total_lines': len(active_lines),
            'date': today_str
        }
        
    except Exception as e:
        logger.error(f'キャッシュウォームアップタスク例外: {str(e)}')
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def refresh_forecast_on_data_change_task(line_id: int, target_date_str: str):
    """
    データ変更時の予測更新タスク（実績データ更新時に呼び出し）
    """
    try:
        from production.services.forecast_service import OptimizedForecastService
        from production.utils import clear_dashboard_cache
        
        target_date = timezone.datetime.strptime(target_date_str, '%Y-%m-%d').date()
        
        # 関連キャッシュをクリア
        clear_dashboard_cache(line_id, target_date_str)
        
        # 予測を再計算
        optimized_service = OptimizedForecastService()
        forecast_time = optimized_service.get_forecast_time(line_id, target_date)
        
        logger.info(f'データ変更時予測更新完了: line={line_id}, date={target_date_str}, time={forecast_time}')
        
        return {
            'success': True,
            'line_id': line_id,
            'target_date': target_date_str,
            'forecast_time': forecast_time
        }
        
    except Exception as e:
        logger.error(f'データ変更時予測更新タスク例外: {str(e)}')
        return {
            'success': False,
            'line_id': line_id,
            'target_date': target_date_str,
            'error': str(e)
        }