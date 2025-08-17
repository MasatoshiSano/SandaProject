"""
終了予測計算コマンド

バックグラウンドで詳細な終了予測を計算し、キャッシュに保存する。
ダッシュボードでは軽量版を使用し、このコマンドで詳細計算を定期実行する。
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import logging

from production.models import Line, ProductionForecastSettings
from production.services.forecast_service import OptimizedForecastService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '終了予測を計算してキャッシュに保存'

    def add_arguments(self, parser):
        parser.add_argument(
            '--line-id',
            type=int,
            help='特定のライン ID を指定'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='対象日付 (YYYY-MM-DD形式)'
        )
        parser.add_argument(
            '--all-active-lines',
            action='store_true',
            help='全ての有効なラインを対象とする'
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=1,
            help='何日先まで計算するか（デフォルト: 1日）'
        )

    def handle(self, *args, **options):
        line_id = options.get('line_id')
        date_str = options.get('date')
        all_active_lines = options.get('all_active_lines')
        days_ahead = options.get('days_ahead')

        # 対象日付の決定
        if date_str:
            try:
                target_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f'無効な日付形式: {date_str}')
                )
                return
        else:
            target_date = timezone.now().date()

        # 対象ラインの決定
        if line_id:
            try:
                lines = [Line.objects.get(id=line_id)]
            except Line.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'ライン ID {line_id} が見つかりません')
                )
                return
        elif all_active_lines:
            lines = Line.objects.filter(is_active=True)
        else:
            # 予測設定が有効なラインのみ
            forecast_settings = ProductionForecastSettings.objects.filter(is_active=True)
            line_ids = [setting.line_id for setting in forecast_settings]
            lines = Line.objects.filter(id__in=line_ids, is_active=True)

        if not lines:
            self.stdout.write(
                self.style.WARNING('対象となるラインがありません')
            )
            return

        # 予測計算サービス（統一）
        from production.services.forecast_service import OptimizedForecastService
        forecast_service = OptimizedForecastService()
        
        total_calculations = 0
        successful_calculations = 0
        
        self.stdout.write(f'最適化予測計算開始: {len(lines)}ライン × {days_ahead}日')

        for line in lines:
            self.stdout.write(f'ライン {line.name} (ID: {line.id}) の計算中...')
            
            for day_offset in range(days_ahead):
                calc_date = target_date + timedelta(days=day_offset)
                
                try:
                    # 全関連キャッシュをクリアして強制再計算
                    self.clear_all_related_cache(line.id, calc_date)
                    result = forecast_service.calculate_completion_forecast(line.id, calc_date)
                    
                    # 結果から時刻を取得
                    if result.get('success') and result.get('completion_time'):
                        forecast_time = result['completion_time'].strftime('%H:%M')
                        if result.get('is_next_day'):
                            forecast_time = f"翌{forecast_time}"
                    elif result.get('success') and not result.get('completion_time'):
                        forecast_time = '実績なし'
                    else:
                        forecast_time = '計算エラー'
                    
                    total_calculations += 1
                    
                    if forecast_time not in ['計算エラー', '計画なし']:
                        successful_calculations += 1
                        self.stdout.write(f'  {calc_date}: {forecast_time}')
                        
                        # 計算成功時にダッシュボード更新通知を送信
                        self.send_dashboard_update_notification(line.id, calc_date)
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'  {calc_date}: {forecast_time}')
                        )
                        
                except Exception as e:
                    total_calculations += 1
                    self.stdout.write(
                        self.style.ERROR(f'  {calc_date}: 例外エラー - {str(e)}')
                    )
                    logger.error(f'最適化予測計算例外 line={line.id}, date={calc_date}: {e}')

        # 結果サマリー
        success_rate = (successful_calculations / total_calculations * 100) if total_calculations > 0 else 0
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n計算完了: {successful_calculations}/{total_calculations} '
                f'({success_rate:.1f}% 成功)'
            )
        )
        
        if successful_calculations > 0:
            self.stdout.write('予測結果がキャッシュに保存されました')
        
        if successful_calculations < total_calculations:
            self.stdout.write(
                self.style.WARNING(
                    f'{total_calculations - successful_calculations}件の計算が失敗しました'
                )
            )
    
    def clear_all_related_cache(self, line_id, calc_date):
        """関連する全てのキャッシュをクリア"""
        from django.core.cache import cache
        from production.utils import clear_dashboard_cache
        
        date_str = calc_date.strftime('%Y-%m-%d')
        
        # 1. ダッシュボードキャッシュをクリア
        clear_dashboard_cache(line_id, date_str)
        
        # 2. 予測関連キャッシュをクリア
        forecast_cache_keys = [
            f"forecast_{line_id}_{calc_date.strftime('%Y%m%d')}",
            f"optimized_forecast_{line_id}_{calc_date.strftime('%Y%m%d')}",
            f"dashboard_data_{line_id}_{date_str}",
            f"current_production_{line_id}*",  # ワイルドカード（後で手動削除）
            f"current_rate_{line_id}*",
            f"part_actuals_{line_id}_{calc_date.strftime('%Y%m%d')}*",
            f"work_calendar_{line_id}",
        ]
        
        # 3. 個別キャッシュをクリア
        for cache_key in forecast_cache_keys:
            if '*' in cache_key:
                # ワイルドカード処理：該当するキーを検索して削除
                self.clear_wildcard_cache(cache_key.replace('*', ''))
            else:
                cache.delete(cache_key)
                
        self.stdout.write(f'  キャッシュクリア完了: {line_id} - {date_str}')
    
    def clear_wildcard_cache(self, prefix):
        """プレフィックスに一致するキャッシュを削除"""
        from django.core.cache import cache
        
        try:
            # Redisキャッシュの場合
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_client'):
                client = cache._cache.get_client()
                keys = client.keys(f"{prefix}*")
                if keys:
                    client.delete(*keys)
            else:
                # 他のキャッシュバックエンドの場合は個別に削除
                # 時間範囲で推測できるキーを削除
                from django.utils import timezone
                now = timezone.now()
                for minutes in range(-60, 61, 5):  # 前後1時間、5分刻み
                    time_key = (now + timedelta(minutes=minutes)).strftime('%Y%m%d%H%M')[:12]
                    cache.delete(f"{prefix}{time_key}")
        except Exception as e:
            logger.warning(f"ワイルドカードキャッシュクリアエラー: {e}")
    
    def send_dashboard_update_notification(self, line_id, calc_date):
        """ダッシュボード更新通知を送信"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            if channel_layer:
                group_name = f'dashboard_{line_id}_{calc_date.strftime("%Y-%m-%d")}'
                
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'dashboard_update',
                        'message': {
                            'type': 'forecast_updated',
                            'line_id': line_id,
                            'date': calc_date.strftime('%Y-%m-%d'),
                            'timestamp': timezone.now().isoformat()
                        }
                    }
                )
                
                self.stdout.write(f'  WebSocket通知送信: {group_name}')
        except Exception as e:
            # WebSocket送信失敗は致命的ではないため、警告のみ
            logger.warning(f"WebSocket通知送信エラー: {e}")