"""
終了予測計算サービス

現在の生産ペースと計画に基づいて、当日の生産終了予測時刻を計算する。
"""

import logging
from datetime import datetime, date, time, timedelta
from typing import Tuple, List, Dict, Optional
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from ..models import (
    Line, Plan, Result, WorkCalendar, PartChangeDowntime, 
    ProductionForecast, ProductionForecastSettings
)

logger = logging.getLogger('production.forecast')


class ForecastCalculationService:
    """終了予測計算サービス（高速化版）"""
    
    def __init__(self):
        self.logger = logger
    
    def calculate_completion_forecast(self, line_id: int, target_date: date) -> dict:
        """
        終了予測時刻を計算（高速化版）
        
        Args:
            line_id: ライン ID
            target_date: 対象日付
            
        Returns:
            dict: 計算結果
        """
        from django.core.cache import cache
        
        # キャッシュキーを生成（5分間キャッシュ）
        cache_key = f"forecast_{line_id}_{target_date.strftime('%Y%m%d')}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            self.logger.debug(f"終了予測をキャッシュから取得: {cache_key}")
            return cached_result
        
        try:
            self.logger.info(f"終了予測計算開始: line={line_id}, date={target_date}")
            
            # 1. 基本データ取得（select_related/prefetch_relatedで最適化）
            line = Line.objects.select_related().get(id=line_id)
            plans = Plan.objects.filter(
                line=line, 
                date=target_date
            ).order_by('sequence').select_related('part', 'part__category').prefetch_related('part__tags')
            
            if not plans.exists():
                result = {
                    'success': True,
                    'completion_time': None,
                    'message': '計画データなし',
                    'confidence': 0
                }
                cache.set(cache_key, result, 300)  # 5分間キャッシュ
                return result
            
            # WorkCalendarをキャッシュから取得
            calendar_cache_key = f"work_calendar_{line_id}"
            work_calendar_data = cache.get(calendar_cache_key)
            if not work_calendar_data:
                try:
                    work_calendar = WorkCalendar.objects.get(line=line)
                    work_calendar_data = {
                        'work_start_time': work_calendar.work_start_time,
                        'morning_meeting_duration': work_calendar.morning_meeting_duration,
                        'break_times': work_calendar.break_times or []
                    }
                except WorkCalendar.DoesNotExist:
                    work_calendar_data = {
                        'work_start_time': time(8, 30),
                        'morning_meeting_duration': 15,
                        'break_times': []
                    }
                cache.set(calendar_cache_key, work_calendar_data, 3600)  # 1時間キャッシュ
            
            # 2. 現在時刻
            now = timezone.now()
            
            # 3. 簡略化された予測計算（line_nameを渡して最適化）
            line_name = line.name
            result = self._calculate_simple_forecast(
                line_id, target_date, plans, work_calendar_data, now, line_name
            )
            
            # キャッシュに保存（5分間）
            cache.set(cache_key, result, 300)
            
            self.logger.info(f"終了予測計算完了: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"終了予測計算エラー line={line_id}: {e}", exc_info=True)
            error_result = {
                'success': False,
                'error': str(e),
                'message': '計算エラー'
            }
            # エラー結果も短時間キャッシュ（1分間）
            cache.set(cache_key, error_result, 60)
            return error_result
    
    def _get_current_production_info(self, plans, now, line_name: str = None) -> Tuple[Optional[object], Decimal]:
        """現在生産中機種の判定と生産速度計算（フォールバック版）"""
        from django.core.cache import cache
        
        if not plans.exists():
            return None, Decimal('0')
        
        # line_nameが渡されていない場合のみ取得
        if line_name is None:
            line_obj = plans.first().line
            line_name = line_obj.name
        
        # キャッシュキーを生成（5分キャッシュ）
        current_time_key = now.strftime('%Y%m%d%H%M')[:12]  # 5分単位でキャッシュ
        cache_key = f"current_production_{line_name}_{current_time_key}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            # キャッシュから計画オブジェクトを再構築
            if cached_result.get('current_part_name'):
                for plan in plans:
                    if plan.part.name == cached_result['current_part_name']:
                        return plan, Decimal(str(cached_result['current_rate']))
            return None, Decimal('0')
        
        # 直近の実績から現在生産中の機種を特定（最適化版）
        try:
            # 時間範囲を短縮してパフォーマンス向上（1時間→15分）
            recent_start_time = (now - timedelta(minutes=15)).strftime('%Y%m%d%H%M%S')
            
            # 最適化クエリ：ORDER BY削除、LIMIT追加
            recent_results = Result.get_filtered_queryset().filter(
                line=line_name,
                timestamp__gte=recent_start_time,
                judgment='1'
            )[:10]  # LIMIT 10でパフォーマンス向上
            
            # リストに変換して存在チェック
            recent_list = list(recent_results)
            
            if not recent_list:
                cache.set(cache_key, {'current_part_name': None, 'current_rate': 0}, 300)
                return None, Decimal('0')
            
            # 最新の実績から現在の機種を判定（ソート不要のため最初の要素を使用）
            latest_result = recent_list[0]
            current_part_name = latest_result.part
            
        except Exception as e:
            self.logger.warning(f"Oracle query error for line {line_name}: {e}")
            cache.set(cache_key, {'current_part_name': None, 'current_rate': 0}, 300)
            return None, Decimal('0')
        
        # 計画に含まれる機種と照合
        current_plan = None
        for plan in plans:
            if plan.part.name == current_part_name:
                current_plan = plan
                break
        
        if not current_plan:
            cache.set(cache_key, {'current_part_name': None, 'current_rate': 0}, 300)
            return None, Decimal('0')
        
        # 当日の実績チェック（最適化された個別クエリ）
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_cache_key = f"today_actuals_{line_name}_{current_part_name}_{today_start.strftime('%Y%m%d')}"
        actual_qty = cache.get(today_cache_key)
        
        if actual_qty is None:
            part_actuals_today = self._get_part_actuals_for_current_production(
                line_name, current_part_name, today_start
            )
            actual_qty = part_actuals_today.get(current_part_name, 0)
            cache.set(today_cache_key, actual_qty, 300)
        
        if actual_qty >= current_plan.planned_quantity:
            cache.set(cache_key, {'current_part_name': None, 'current_rate': 0}, 300)
            return None, Decimal('0')
        
        # 生産速度計算（最適化）
        # 最近10分の実績をカウント（時間範囲短縮）
        recent_10min_start = (now - timedelta(minutes=10)).strftime('%Y%m%d%H%M%S')
        recent_10min_count = sum(1 for result in recent_list 
                               if result.part == current_part_name 
                               and result.timestamp >= recent_10min_start)
        
        if recent_10min_count > 0:
            current_rate = Decimal(str((recent_10min_count / 10) * 60))  # 時間当たりに換算
            
            # 異常値チェック
            planned_pph = current_plan.part.target_pph or 10
            if current_rate <= 0 or current_rate > planned_pph * 3:
                current_rate = Decimal(str(planned_pph))
        else:
            current_rate = Decimal(str(current_plan.part.target_pph or 10))
        
        # キャッシュに保存
        cache.set(cache_key, {
            'current_part_name': current_part_name,
            'current_rate': float(current_rate)
        }, 300)
        
        return current_plan, current_rate
    
    def _calculate_work_hours_elapsed(self, now):
        """現在時刻から経過した作業時間を計算"""
        # 8:30開始と仮定
        work_start = now.replace(hour=8, minute=30, second=0, microsecond=0)
        
        if now < work_start:
            return 0  # 勤務時間前
        
        elapsed = now - work_start
        elapsed_hours = elapsed.total_seconds() / 3600
        
        # 朝礼時間（15分）を除く
        adjusted_hours = max(0, elapsed_hours - 0.25)
        
        return adjusted_hours
    
    def _find_continuous_production_start(self, results, current_time) -> datetime:
        """連続生産開始時刻を見つける"""
        if not results.exists():
            return current_time
        
        # 最新の実績から遡って、5分以上の間隔がある時点を探す
        prev_time = current_time
        continuous_start = current_time
        
        for result in results:
            # 文字列形式のタイムスタンプをdatetimeに変換
            try:
                result_time = datetime.strptime(result.timestamp, '%Y%m%d%H%M%S')
                # タイムゾーンを統一
                if timezone.is_aware(current_time):
                    result_time = timezone.make_aware(result_time)
                
                time_gap = prev_time - result_time
                if time_gap > timedelta(minutes=5):  # 5分以上の間隔で生産中断と判定
                    break
                continuous_start = result_time
                prev_time = result_time
            except ValueError:
                # タイムスタンプの形式が不正な場合はスキップ
                continue
        
        return continuous_start
    
    def _estimate_completion_time_with_breaks(
        self, start_time: datetime, remaining_work: List[Dict], work_calendar
    ) -> Tuple[Optional[time], int]:
        """休憩時間を考慮した完了時刻推定"""
        # タイムゾーンを統一（start_timeがaware datetimeの場合）
        current_time = start_time
        confidence = 100  # 信頼度（%）
        
        for i, work in enumerate(remaining_work):
            # 段替え時間の取得と追加
            setup_minutes = self._get_setup_time(work, remaining_work, i)
            if setup_minutes > 0:
                current_time = self._add_time_with_breaks(
                    current_time, setup_minutes, work_calendar, is_setup=True
                )
            
            # 生産時間の計算と追加
            if work['rate'] > 0:
                production_minutes = (work['quantity'] / work['rate']) * 60
                current_time = self._add_time_with_breaks(
                    current_time, production_minutes, work_calendar, is_setup=False
                )
            
            # 信頼度調整（より現実的な計算）
            if work['is_current']:
                confidence *= 0.95  # 現在生産中でも5%の不確実性
            else:
                # 未来の機種：計画からの乖離可能性を考慮
                confidence *= 0.85  # 15%の不確実性
        
        return current_time.time(), max(round(confidence), 10)  # 最低10%の信頼度
    
    def _get_setup_time(self, current_work: Dict, remaining_work: List[Dict], current_index: int) -> float:
        """段替え時間をPartChangeDowntimeテーブルから取得"""
        if current_work.get('is_current', False):
            return 0  # 現在生産中なら段替え不要
        
        if current_index == 0:
            return 0  # 最初の機種
        
        from_part = remaining_work[current_index - 1]['part']
        to_part = current_work['part']
        
        try:
            downtime = PartChangeDowntime.objects.get(
                line=current_work['plan'].line,
                from_part=from_part,
                to_part=to_part
            )
            return downtime.downtime_seconds / 60  # 分に変換
        except PartChangeDowntime.DoesNotExist:
            # デフォルト段替え時間（30分）
            return 30
    
    def _add_time_with_breaks(
        self, start_time: datetime, duration_minutes: float, 
        work_calendar, is_setup: bool = False
    ) -> datetime:
        """休憩時間を考慮して時間を追加"""
        current_time = start_time
        remaining_minutes = duration_minutes
        break_times = work_calendar.break_times or []
        
        while remaining_minutes > 0:
            # 次の休憩時間を取得
            next_break = self._get_next_break(current_time, break_times)
            
            if next_break:
                # 日またぎ対応の休憩時刻計算
                break_start_time = datetime.strptime(next_break['start'], '%H:%M').time()
                break_end_time = datetime.strptime(next_break['end'], '%H:%M').time()
                
                # 現在時刻の日付を基準に休憩時刻を計算
                current_date = current_time.date()
                break_start = datetime.combine(current_date, break_start_time)
                break_end = datetime.combine(current_date, break_end_time)
                
                # current_timeがタイムゾーン付きの場合、休憩時間もタイムゾーン付きにする
                if timezone.is_aware(current_time):
                    break_start = timezone.make_aware(break_start)
                    break_end = timezone.make_aware(break_end)
                
                # 休憩終了時刻が開始時刻より早い場合（日またぎ）
                if break_end_time < break_start_time:
                    break_end = break_end + timedelta(days=1)
                
                # 現在時刻が休憩開始時刻より前の日の場合、翌日の休憩とする
                # タイムゾーンを統一してから比較
                if timezone.is_aware(current_time):
                    break_start = timezone.make_aware(break_start) if timezone.is_naive(break_start) else break_start
                    break_end = timezone.make_aware(break_end) if timezone.is_naive(break_end) else break_end
                else:
                    break_start = timezone.make_naive(break_start) if timezone.is_aware(break_start) else break_start
                    break_end = timezone.make_naive(break_end) if timezone.is_aware(break_end) else break_end
                
                if current_time > break_start + timedelta(hours=12):
                    break_start = break_start + timedelta(days=1)
                    break_end = break_end + timedelta(days=1)
                
                # 休憩までの時間
                minutes_until_break = max(0, (break_start - current_time).total_seconds() / 60)
                
                if minutes_until_break > 0:
                    # 休憩まで作業可能
                    work_minutes = min(remaining_minutes, minutes_until_break)
                    current_time += timedelta(minutes=work_minutes)
                    remaining_minutes -= work_minutes
                    
                    # まだ残り時間がある場合は休憩
                    if remaining_minutes > 0:
                        # 段替え・生産ともに休憩中は完全停止
                        current_time = break_end
                else:
                    # 既に休憩時間内の場合
                    current_time = max(current_time, break_end)
            else:
                # これ以上休憩がない場合
                current_time += timedelta(minutes=remaining_minutes)
                remaining_minutes = 0
        
        return current_time
    
    def _get_next_break(self, current_time: datetime, break_times: List[Dict]) -> Optional[Dict]:
        """次の休憩時間を取得（日またぎ対応）"""
        if not break_times:
            return None
        
        current_time_only = current_time.time()
        
        # 当日の休憩時間をチェック
        for break_info in break_times:
            break_start = datetime.strptime(break_info['start'], '%H:%M').time()
            break_end = datetime.strptime(break_info['end'], '%H:%M').time()
            
            # 日またぎ休憩の処理
            if break_end < break_start:
                # 例：23:00-01:00の休憩
                if current_time_only >= break_start or current_time_only < break_end:
                    return break_info
            else:
                # 通常の休憩
                if current_time_only < break_start:
                    return break_info
        
        # 当日に該当する休憩がない場合、翌日の最初の休憩を返す
        if break_times:
            return break_times[0]
        
        return None
    
    def _get_part_actuals_for_current_production(self, line_name: str, part_name: str, start_time: datetime) -> Dict[str, int]:
        """現在生産情報用の実績取得（最適化）"""
        from django.db.models import Count
        
        try:
            end_time = start_time + timedelta(days=1)
            
            results = Result.get_filtered_queryset().filter(
                line=line_name,
                part=part_name,
                judgment='1',
                timestamp__gte=start_time.strftime('%Y%m%d%H%M%S'),
                timestamp__lt=end_time.strftime('%Y%m%d%H%M%S')
            ).aggregate(
                total_count=Count('serial_number')
            )
            
            return {part_name: results['total_count'] or 0}
            
        except Exception as e:
            self.logger.error(f"現在生産実績取得エラー: {e}")
            return {part_name: 0}
    
    def _get_all_part_actuals_bulk(self, line_id: int, target_date: date, plans, line_name: str = None) -> Dict[str, int]:
        """全機種の実績を一括取得（最適化版）"""
        from django.db.models import Count
        from django.core.cache import cache
        
        # line_nameが渡されていない場合のみLineオブジェクトを取得
        if line_name is None:
            line_obj = Line.objects.get(id=line_id)
            line_name = line_obj.name
        
        start_time = target_date.strftime('%Y%m%d') + '000000'
        end_time = (target_date + timedelta(days=1)).strftime('%Y%m%d') + '000000'
        
        # 計画に含まれる機種名を取得（既にselect_relatedされているのでDBアクセス不要）
        part_names = [plan.part.name for plan in plans]
        
        if not part_names:
            return {}
        
        # キャッシュキーを生成（30分キャッシュ）
        part_names_hash = hash(tuple(sorted(part_names)))
        cache_key = f"part_actuals_{line_id}_{target_date.strftime('%Y%m%d')}_{part_names_hash}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            self.logger.debug(f"実績データをキャッシュから取得: {cache_key}")
            return cached_result
        
        try:
            # Oracle複雑クエリを分割方式で最適化
            self.logger.debug(f"Oracle分割クエリでの実績取得開始: {len(part_names)}機種")
            
            part_actuals = {}
            
            # 機種ごとに個別クエリで実績取得（ORDER BY削除でパフォーマンス向上）
            for part_name in part_names:
                try:
                    # シンプルな単一機種クエリ（ORDER BY なし）
                    count = Result.get_filtered_queryset().filter(
                        line=line_name,
                        part=part_name,  # 単一値検索（IN句回避）
                        judgment='1',
                        timestamp__gte=start_time,
                        timestamp__lt=end_time
                    ).count()  # 単純カウント（集計処理簡素化）
                    
                    part_actuals[part_name] = count
                    self.logger.debug(f"実績取得完了: {part_name} = {count}件")
                    
                except Exception as e:
                    self.logger.warning(f"機種別実績取得エラー {part_name}: {e}")
                    part_actuals[part_name] = 0
            
            # キャッシュに保存（30分）
            cache.set(cache_key, part_actuals, 1800)
            
            return part_actuals
            
        except Exception as e:
            self.logger.error(f"一括実績取得エラー: {e}")
            # フォールバック: 空の辞書を返す
            return {part_name: 0 for part_name in part_names}
    
    def _is_next_work_day(self, completion_time: Optional[time], work_calendar, target_date: date) -> bool:
        """翌作業日かどうかの判定（夜勤対応）"""
        if not completion_time:
            return False
        
        completion_datetime = datetime.combine(target_date, completion_time)
        work_start_time = work_calendar.work_start_time
        
        # 翌日の作業開始時刻
        next_day_start = datetime.combine(target_date + timedelta(days=1), work_start_time)
        
        # 夜勤判定：作業開始時刻が22:00以降または6:00以前
        is_night_shift = work_start_time >= time(22, 0) or work_start_time <= time(6, 0)
        
        if is_night_shift:
            # 夜勤の場合：翌日の作業開始時刻を超えたら翌作業日
            return completion_datetime >= next_day_start
        else:
            # 日勤の場合：翌日の作業開始時刻を超えたら翌作業日
            return completion_datetime >= next_day_start    

    def _calculate_simple_forecast(self, line_id: int, target_date: date, plans, work_calendar_data: dict, now: datetime, line_name: str = None) -> dict:
        """簡略化された予測計算（高速版）"""
        try:
            # 1. 全機種の実績を一括取得（最適化版）
            if line_name is None:
                line_obj = Line.objects.get(id=line_id)
                line_name = line_obj.name
            part_actuals = self._get_all_part_actuals_bulk(line_id, target_date, plans, line_name)
            
            # 2. 残り作業量と総時間を計算
            total_planned = 0
            total_actual = 0
            total_remaining_minutes = 0
            has_remaining_work = False
            
            for plan in plans:
                part_name = plan.part.name
                planned_qty = plan.planned_quantity
                actual_qty = part_actuals.get(part_name, 0)
                remaining_qty = max(0, planned_qty - actual_qty)
                
                total_planned += planned_qty
                total_actual += actual_qty
                
                if remaining_qty > 0:
                    has_remaining_work = True
                    # 簡略化：目標PPHベースで時間計算（段替え時間は平均15分を加算）
                    target_pph = plan.part.target_pph or 10
                    production_minutes = (remaining_qty / target_pph) * 60
                    setup_minutes = 15  # 平均段替え時間
                    total_remaining_minutes += production_minutes + setup_minutes
            
            if not has_remaining_work:
                return {
                    'success': True,
                    'completion_time': now.time(),
                    'message': '生産完了済み',
                    'confidence': 100,
                    'is_delayed': False,
                    'is_next_day': False,
                    'current_rate': 0,
                    'total_planned': total_planned,
                    'total_actual': total_actual
                }
            
            # 3. 正確な完了時刻計算（休憩時間を考慮）
            completion_datetime = self._calculate_completion_with_actual_breaks(
                now, total_remaining_minutes, work_calendar_data
            )
            completion_time = completion_datetime.time()
            
            # 4. 遅延・翌日判定
            work_start_time = work_calendar_data['work_start_time']
            is_delayed = completion_time > time(17, 0)
            
            # 翌日判定：翌日の作業開始時刻を超えるか
            next_day_start = datetime.combine(target_date + timedelta(days=1), work_start_time)
            is_next_day = completion_datetime >= timezone.make_aware(next_day_start) if timezone.is_aware(completion_datetime) else completion_datetime >= next_day_start
            
            # 5. 信頼度計算（簡略化）
            achievement_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
            if achievement_rate >= 80:
                confidence = 85
            elif achievement_rate >= 50:
                confidence = 70
            else:
                confidence = 50
            
            # 6. 現在の生産速度（最適化版）
            current_rate = self._get_current_rate_simple(line_id, now, line_name)
            
            # 7. 結果保存（非同期で実行可能）
            self._save_forecast_async(
                line_id, target_date, completion_time, now, current_rate,
                total_planned, total_actual, is_delayed, confidence, is_next_day
            )
            
            return {
                'success': True,
                'completion_time': completion_time,
                'is_delayed': is_delayed,
                'is_next_day': is_next_day,
                'current_rate': float(current_rate),
                'confidence': confidence,
                'total_planned': total_planned,
                'total_actual': total_actual
            }
            
        except Exception as e:
            self.logger.error(f"簡略予測計算エラー: {e}")
            raise
    
    def _calculate_completion_with_actual_breaks(self, start_time: datetime, total_minutes: float, work_calendar_data: dict) -> datetime:
        """実際の休憩時間を考慮した完了時刻計算"""
        current_time = start_time
        remaining_minutes = total_minutes
        break_times = work_calendar_data.get('break_times', [])
        
        while remaining_minutes > 0:
            # 次の休憩時間を取得
            next_break = self._get_next_break_simple(current_time, break_times)
            
            if next_break:
                # 休憩開始時刻を計算
                break_start_time = datetime.strptime(next_break['start'], '%H:%M').time()
                break_end_time = datetime.strptime(next_break['end'], '%H:%M').time()
                
                current_date = current_time.date()
                break_start = datetime.combine(current_date, break_start_time)
                break_end = datetime.combine(current_date, break_end_time)
                
                # タイムゾーンを統一
                if timezone.is_aware(current_time):
                    break_start = timezone.make_aware(break_start)
                    break_end = timezone.make_aware(break_end)
                
                # 日またぎ休憩の処理
                if break_end_time < break_start_time:
                    break_end = break_end + timedelta(days=1)
                
                # 現在時刻が休憩開始より前の場合
                if current_time < break_start:
                    # 休憩まで作業可能な時間
                    minutes_until_break = (break_start - current_time).total_seconds() / 60
                    
                    if remaining_minutes <= minutes_until_break:
                        # 休憩前に完了
                        return current_time + timedelta(minutes=remaining_minutes)
                    else:
                        # 休憩まで作業して、休憩後に継続
                        remaining_minutes -= minutes_until_break
                        current_time = break_end  # 休憩終了時刻にジャンプ
                else:
                    # 既に休憩時間内または休憩後の場合
                    if current_time < break_end:
                        current_time = break_end  # 休憩終了まで待機
            else:
                # これ以上休憩がない場合
                return current_time + timedelta(minutes=remaining_minutes)
        
        return current_time
    
    def _get_next_break_simple(self, current_time: datetime, break_times: list) -> dict:
        """次の休憩時間を取得（簡略版）"""
        if not break_times:
            return None
        
        current_time_only = current_time.time()
        
        # 当日の休憩時間をチェック
        for break_info in break_times:
            break_start = datetime.strptime(break_info['start'], '%H:%M').time()
            break_end = datetime.strptime(break_info['end'], '%H:%M').time()
            
            # 日またぎ休憩の処理
            if break_end < break_start:
                # 例：23:00-00:00の休憩
                if current_time_only >= break_start or current_time_only < break_end:
                    return break_info
            else:
                # 通常の休憩
                if current_time_only < break_start:
                    return break_info
        
        # 当日に該当する休憩がない場合、翌日の最初の休憩を返す
        if break_times:
            return break_times[0]
        
        return None
    
    def _get_all_part_actuals_bulk_optimized(self, line_id: int, target_date: date, plans) -> dict:
        """全機種の実績を一括取得（最適化版）"""
        from django.db.models import Count
        from django.core.cache import cache
        
        # キャッシュキーを生成
        cache_key = f"part_actuals_{line_id}_{target_date.strftime('%Y%m%d')}"
        cached_actuals = cache.get(cache_key)
        
        if cached_actuals is not None:
            return cached_actuals
        
        try:
            line_obj = Line.objects.get(id=line_id)
            line_name = line_obj.name
            start_str = target_date.strftime('%Y%m%d') + '000000'
            end_str = (target_date + timedelta(days=1)).strftime('%Y%m%d') + '000000'
            
            # 計画に含まれる機種名を取得
            part_names = [plan.part.name for plan in plans]
            
            if not part_names:
                return {}
            
            # 一括でGROUP BYクエリを実行
            results = Result.objects.using('oracle').filter(
                line=line_name,
                part__in=part_names,
                judgment='1',
                timestamp__gte=start_str,
                timestamp__lt=end_str,
                sta_no1='SAND'
            ).values('part').annotate(
                actual_count=Count('serial_number')
            )
            
            # 辞書形式で返却
            part_actuals = {result['part']: result['actual_count'] for result in results}
            
            # 実績がない機種は0で初期化
            for part_name in part_names:
                if part_name not in part_actuals:
                    part_actuals[part_name] = 0
            
            # キャッシュに保存（10分間）
            cache.set(cache_key, part_actuals, 600)
            
            return part_actuals
            
        except Exception as e:
            self.logger.error(f"最適化実績取得エラー: {e}")
            # フォールバック: 空の辞書を返す
            return {plan.part.name: 0 for plan in plans}
    
    def _get_current_rate_simple(self, line_id: int, now: datetime, line_name: str = None) -> float:
        """現在の生産速度を簡単に取得（最適化版）"""
        from django.core.cache import cache
        
        cache_key = f"current_rate_{line_id}_{now.strftime('%Y%m%d%H%M')[:12]}"  # 5分単位
        cached_rate = cache.get(cache_key)
        
        if cached_rate is not None:
            return cached_rate
        
        try:
            # line_nameが渡されていない場合のみLineオブジェクト取得
            if line_name is None:
                line_obj = Line.objects.get(id=line_id)
                line_name = line_obj.name
            
            # 直近30分の実績から速度を計算
            recent_30min = (now - timedelta(minutes=30)).strftime('%Y%m%d%H%M%S')
            now_str = now.strftime('%Y%m%d%H%M%S')
            
            recent_count = Result.objects.using('oracle').filter(
                line=line_name,
                judgment='1',
                timestamp__gte=recent_30min,
                timestamp__lt=now_str,
                sta_no1='SAND'
            ).count()
            
            # 時間当たりに換算
            current_rate = (recent_count / 30) * 60 if recent_count > 0 else 0
            
            # 異常値チェック（0-300の範囲）
            current_rate = max(0, min(current_rate, 300))
            
            # キャッシュに保存（5分間）
            cache.set(cache_key, current_rate, 300)
            
            return current_rate
            
        except Exception as e:
            self.logger.error(f"現在速度取得エラー: {e}")
            return 0
    
    def _save_forecast_async(self, line_id: int, target_date: date, completion_time, 
                           calculation_time: datetime, current_rate: float,
                           total_planned: int, total_actual: int, is_delayed: bool,
                           confidence: int, is_next_day: bool):
        """予測結果を非同期で保存"""
        try:
            from django.db import transaction
            
            def save_forecast():
                line = Line.objects.get(id=line_id)
                ProductionForecast.objects.update_or_create(
                    line=line,
                    target_date=target_date,
                    defaults={
                        'forecast_completion_time': completion_time,
                        'calculation_timestamp': calculation_time,
                        'current_production_rate': current_rate,
                        'total_planned_quantity': total_planned,
                        'total_actual_quantity': total_actual,
                        'is_delayed': is_delayed,
                        'confidence_level': confidence,
                        'is_next_day': is_next_day,
                        'error_message': ''
                    }
                )
            
            # トランザクション完了後に実行
            transaction.on_commit(save_forecast)
            
        except Exception as e:
            self.logger.error(f"予測結果保存エラー: {e}")
    
    def get_cached_forecast(self, line_id: int, target_date: date) -> dict:
        """キャッシュされた予測結果を取得"""
        from django.core.cache import cache
        
        cache_key = f"forecast_{line_id}_{target_date.strftime('%Y%m%d')}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        # キャッシュがない場合はDBから取得
        try:
            forecast = ProductionForecast.objects.get(
                line_id=line_id,
                target_date=target_date
            )
            
            result = {
                'success': True,
                'completion_time': forecast.forecast_completion_time,
                'is_delayed': forecast.is_delayed,
                'is_next_day': forecast.is_next_day,
                'current_rate': float(forecast.current_production_rate or 0),
                'confidence': forecast.confidence_level,
                'total_planned': forecast.total_planned_quantity,
                'total_actual': forecast.total_actual_quantity
            }
            
            # キャッシュに保存
            cache.set(cache_key, result, 300)
            return result
            
        except ProductionForecast.DoesNotExist:
            return {
                'success': True,
                'completion_time': None,
                'message': '予測データなし',
                'confidence': 0
            }
    
    def clear_forecast_cache(self, line_id: int, target_date: date = None):
        """予測関連のキャッシュをクリア"""
        from django.core.cache import cache
        
        if target_date:
            date_str = target_date.strftime('%Y%m%d')
        else:
            date_str = timezone.now().date().strftime('%Y%m%d')
        
        cache_keys = [
            f"forecast_{line_id}_{date_str}",
            f"part_actuals_{line_id}_{date_str}",
            f"current_rate_{line_id}",
            f"work_calendar_{line_id}"
        ]
        
        cache.delete_many(cache_keys)
        self.logger.info(f"予測キャッシュをクリア: line_id={line_id}, date={date_str}")


# 軽量版の予測サービス
class OptimizedForecastService:
    """最適化された終了予測サービス（休憩・段替え時間を正確に反映）"""
    
    def __init__(self):
        self.logger = logger
    
    def get_forecast_time(self, line_id: int, target_date: date) -> str:
        """予測時刻を取得（15分間キャッシュ）"""
        from django.core.cache import cache
        
        # 古いキャッシュを自動クリア（サービス切り替え対応）
        self._clear_old_forecast_cache(line_id, target_date)
        
        cache_key = f"optimized_forecast_{line_id}_{target_date.strftime('%Y%m%d')}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            self.logger.debug(f"予測時刻をキャッシュから取得: {cache_key}")
            return cached_result
        
        try:
            result = self._calculate_forecast_with_breaks(line_id, target_date)
            
            # 15分間キャッシュ
            cache.set(cache_key, result, 900)
            
            return result
            
        except Exception as e:
            self.logger.error(f"最適化予測計算エラー: {e}")
            error_result = '計算エラー'
            # エラー結果も短時間キャッシュ（5分間）
            cache.set(cache_key, error_result, 300)
            return error_result
    
    def _calculate_forecast_with_breaks(self, line_id: int, target_date: date) -> str:
        """休憩・段替え時間を正確に反映した予測計算"""
        from django.core.cache import cache
        
        # 1. 基本データを一括取得（キャッシュ活用）
        basic_data = self._get_basic_data_cached(line_id, target_date)
        if not basic_data['plans']:
            return '計画なし'
        
        plans = basic_data['plans']
        work_calendar = basic_data['work_calendar']
        
        # 2. 実績データを一括取得
        part_actuals = self._get_part_actuals_optimized(line_id, target_date, plans)
        
        # 3. 残り作業を計算
        remaining_work = []
        for plan in plans:
            actual_qty = part_actuals.get(plan.part.name, 0)
            remaining_qty = max(0, plan.planned_quantity - actual_qty)
            
            if remaining_qty > 0:
                remaining_work.append({
                    'part': plan.part,
                    'quantity': remaining_qty,
                    'target_pph': plan.part.target_pph or 10,
                    'sequence': plan.sequence
                })
        
        if not remaining_work:
            return '完了済み'
        
        # 4. 現在時刻から計算開始
        now = timezone.now()
        current_time = now
        
        # 5. 各作業の完了時刻を計算（休憩・段替え時間込み）
        for i, work in enumerate(remaining_work):
            # 段替え時間を追加
            if i > 0:
                setup_minutes = self._get_setup_time_cached(
                    line_id, remaining_work[i-1]['part'], work['part']
                )
                current_time = self._add_time_with_breaks_optimized(
                    current_time, setup_minutes, work_calendar
                )
            
            # 生産時間を追加
            production_minutes = (work['quantity'] / work['target_pph']) * 60
            current_time = self._add_time_with_breaks_optimized(
                current_time, production_minutes, work_calendar
            )
        
        return current_time.strftime('%H:%M')
    
    def _get_basic_data_cached(self, line_id: int, target_date: date) -> dict:
        """基本データをキャッシュから取得"""
        from django.core.cache import cache
        
        # 計画データのキャッシュ
        plans_cache_key = f"plans_{line_id}_{target_date.strftime('%Y%m%d')}"
        cached_plans = cache.get(plans_cache_key)
        
        if cached_plans is None:
            plans = list(Plan.objects.filter(
                line_id=line_id, 
                date=target_date
            ).select_related('part').order_by('sequence'))
            cache.set(plans_cache_key, plans, 3600)  # 1時間キャッシュ
        else:
            plans = cached_plans
        
        # 作業カレンダーのキャッシュ
        calendar_cache_key = f"work_calendar_{line_id}"
        work_calendar = cache.get(calendar_cache_key)
        
        if work_calendar is None:
            try:
                wc = WorkCalendar.objects.get(line_id=line_id)
                work_calendar = {
                    'work_start_time': wc.work_start_time,
                    'morning_meeting_duration': wc.morning_meeting_duration,
                    'break_times': wc.break_times or []
                }
            except WorkCalendar.DoesNotExist:
                work_calendar = {
                    'work_start_time': time(8, 30),
                    'morning_meeting_duration': 15,
                    'break_times': [
                        {"start": "10:45", "end": "11:00"},
                        {"start": "12:00", "end": "12:45"},
                        {"start": "15:00", "end": "15:15"}
                    ]
                }
            cache.set(calendar_cache_key, work_calendar, 3600)  # 1時間キャッシュ
        
        return {
            'plans': plans,
            'work_calendar': work_calendar
        }
    
    def _get_part_actuals_optimized(self, line_id: int, target_date: date, plans) -> dict:
        """機種別実績を最適化クエリで取得"""
        from django.core.cache import cache
        from django.db.models import Count
        
        cache_key = f"part_actuals_opt_{line_id}_{target_date.strftime('%Y%m%d')}"
        cached_actuals = cache.get(cache_key)
        
        if cached_actuals is not None:
            return cached_actuals
        
        try:
            line_obj = Line.objects.get(id=line_id)
            line_name = line_obj.name
            part_names = [plan.part.name for plan in plans]
            
            if not part_names:
                return {}
            
            # 日付範囲を設定
            start_str = target_date.strftime('%Y%m%d') + '000000'
            end_str = (target_date + timedelta(days=1)).strftime('%Y%m%d') + '000000'
            
            # 一括クエリで実績を取得
            results = Result.objects.using('oracle').filter(
                line=line_name,
                part__in=part_names,
                judgment='1',
                timestamp__gte=start_str,
                timestamp__lt=end_str,
                sta_no1='SAND'
            ).values('part').annotate(
                count=Count('serial_number')
            )
            
            part_actuals = {r['part']: r['count'] for r in results}
            
            # 実績がない機種は0で初期化
            for part_name in part_names:
                if part_name not in part_actuals:
                    part_actuals[part_name] = 0
            
            # 10分間キャッシュ
            cache.set(cache_key, part_actuals, 600)
            
            return part_actuals
            
        except Exception as e:
            self.logger.error(f"実績取得エラー: {e}")
            return {plan.part.name: 0 for plan in plans}
    
    def _get_setup_time_cached(self, line_id: int, from_part, to_part) -> float:
        """段替え時間をキャッシュから取得"""
        from django.core.cache import cache
        
        cache_key = f"setup_time_{line_id}_{from_part.id}_{to_part.id}"
        cached_time = cache.get(cache_key)
        
        if cached_time is not None:
            return cached_time
        
        try:
            downtime = PartChangeDowntime.objects.get(
                line_id=line_id,
                from_part=from_part,
                to_part=to_part
            )
            setup_minutes = downtime.downtime_seconds / 60
        except PartChangeDowntime.DoesNotExist:
            # デフォルト段替え時間（機種が異なる場合は30分、同じ場合は0分）
            setup_minutes = 30 if from_part.id != to_part.id else 0
        
        # 1時間キャッシュ
        cache.set(cache_key, setup_minutes, 3600)
        
        return setup_minutes
    
    def _add_time_with_breaks_optimized(self, start_time: datetime, duration_minutes: float, work_calendar: dict) -> datetime:
        """休憩時間を考慮して時間を追加（最適化版）"""
        if duration_minutes <= 0:
            return start_time
        
        current_time = start_time
        remaining_minutes = duration_minutes
        break_times = work_calendar.get('break_times', [])
        
        # 休憩時間を事前に計算してソート
        daily_breaks = []
        current_date = current_time.date()
        
        for break_info in break_times:
            try:
                break_start_time = datetime.strptime(break_info['start'], '%H:%M').time()
                break_end_time = datetime.strptime(break_info['end'], '%H:%M').time()
                
                break_start = datetime.combine(current_date, break_start_time)
                break_end = datetime.combine(current_date, break_end_time)
                
                # タイムゾーン統一
                if timezone.is_aware(current_time):
                    break_start = timezone.make_aware(break_start)
                    break_end = timezone.make_aware(break_end)
                
                # 日またぎ休憩の処理
                if break_end_time < break_start_time:
                    break_end = break_end + timedelta(days=1)
                
                daily_breaks.append((break_start, break_end))
                
            except ValueError:
                continue
        
        # 休憩時間を開始時刻順にソート
        daily_breaks.sort(key=lambda x: x[0])
        
        # 作業時間を休憩を考慮して追加
        for break_start, break_end in daily_breaks:
            if current_time >= break_end:
                continue  # 既に過ぎた休憩
            
            if remaining_minutes <= 0:
                break
            
            # 休憩開始までの作業可能時間
            if current_time < break_start:
                available_minutes = (break_start - current_time).total_seconds() / 60
                work_minutes = min(remaining_minutes, available_minutes)
                
                current_time += timedelta(minutes=work_minutes)
                remaining_minutes -= work_minutes
                
                # まだ残り時間があり、休憩時間に入る場合
                if remaining_minutes > 0 and current_time >= break_start:
                    current_time = break_end
            else:
                # 既に休憩時間内の場合
                current_time = max(current_time, break_end)
        
        # 残り時間を追加
        if remaining_minutes > 0:
            current_time += timedelta(minutes=remaining_minutes)
        
        return current_time
    
    def clear_cache(self, line_id: int, target_date: date = None):
        """予測関連キャッシュをクリア"""
        from django.core.cache import cache
        
        if target_date is None:
            target_date = timezone.now().date()
        
        date_str = target_date.strftime('%Y%m%d')
        
        cache_keys = [
            f"optimized_forecast_{line_id}_{date_str}",
            f"part_actuals_opt_{line_id}_{date_str}",
            f"plans_{line_id}_{date_str}",
            f"work_calendar_{line_id}"
        ]
        
        # 段替え時間のキャッシュもクリア（パターンマッチング）
        try:
            from django.core.cache.backends.base import DEFAULT_TIMEOUT
            # 段替え時間キャッシュは個別にクリアが困難なため、必要に応じて全体クリア
            pass
        except:
            pass
        
        cache.delete_many(cache_keys)
        self.logger.info(f"最適化予測キャッシュクリア: line_id={line_id}, date={date_str}")
    
    def _clear_old_forecast_cache(self, line_id: int, target_date: date):
        """古い予測サービスのキャッシュを自動クリア"""
        from django.core.cache import cache
        
        date_str = target_date.strftime('%Y%m%d')
        
        # 古いForecastCalculationServiceのキャッシュキーをクリア
        old_cache_keys = [
            f"forecast_{line_id}_{date_str}",  # 古いサービスのキャッシュ
            f"dashboard_data_{line_id}_{date_str}",  # ダッシュボードキャッシュ
            f"enhanced_dashboard_{line_id}_{date_str}",  # 強化ダッシュボードキャッシュ
        ]
        
        cache.delete_many(old_cache_keys)
        self.logger.debug(f"古いキャッシュクリア: {old_cache_keys}")