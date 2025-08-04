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
    """終了予測計算サービス"""
    
    def __init__(self):
        self.logger = logger
    
    def calculate_completion_forecast(self, line_id: int, target_date: date) -> dict:
        """
        終了予測時刻を計算
        
        Args:
            line_id: ライン ID
            target_date: 対象日付
            
        Returns:
            dict: 計算結果
        """
        try:
            self.logger.info(f"終了予測計算開始: line={line_id}, date={target_date}")
            
            # 1. 基本データ取得
            line = Line.objects.get(id=line_id)
            plans = Plan.objects.filter(
                line=line, 
                date=target_date
            ).order_by('sequence').select_related('part')
            
            if not plans.exists():
                return {
                    'success': True,
                    'completion_time': None,
                    'message': '計画データなし',
                    'confidence': 0
                }
            
            work_calendar = WorkCalendar.objects.get(line=line)
            
            # 2. 現在時刻と現在の生産状況
            now = timezone.now()
            
            # 3. 現在生産中機種の判定と生産速度計算
            current_production_part, current_rate = self._get_current_production_info(plans, now)
            
            # 4. 残り作業量計算
            remaining_work = []
            current_part_found = False
            
            for plan in plans:
                actual_qty = plan.results.aggregate(
                    total=Sum('quantity')
                )['total'] or 0
                remaining_qty = plan.quantity - actual_qty
                
                if remaining_qty > 0:
                    # 現在生産中機種か判定
                    is_current = (
                        current_production_part and 
                        plan.part.id == current_production_part.id and 
                        not current_part_found
                    )
                    
                    if is_current:
                        current_part_found = True
                        production_rate = current_rate
                    else:
                        production_rate = plan.planned_pph or 10  # デフォルト値
                    
                    remaining_work.append({
                        'plan': plan,
                        'part': plan.part,
                        'quantity': remaining_qty,
                        'rate': production_rate,
                        'is_current': is_current
                    })
            
            if not remaining_work:
                return {
                    'success': True,
                    'completion_time': now.time(),
                    'message': '生産完了済み',
                    'confidence': 100,
                    'is_delayed': False,
                    'is_next_day': False,
                    'current_rate': current_rate
                }
            
            # 5. 休憩時間・段替え時間考慮した完了時刻計算
            completion_time, confidence = self._estimate_completion_time_with_breaks(
                now, remaining_work, work_calendar
            )
            
            # 6. 翌日判定（work_start_timeベース）
            is_next_day = self._is_next_work_day(completion_time, work_calendar, target_date)
            
            # 7. 遅延判定（17:00基準、将来的にはwork_calendarベース）
            is_delayed = completion_time and completion_time > time(17, 0)
            
            # 8. 結果保存
            forecast, created = ProductionForecast.objects.update_or_create(
                line=line,
                target_date=target_date,
                defaults={
                    'forecast_completion_time': completion_time,
                    'calculation_timestamp': now,
                    'current_production_rate': current_rate,
                    'total_planned_quantity': sum(p.quantity for p in plans),
                    'total_actual_quantity': sum(
                        p.results.aggregate(total=Sum('quantity'))['total'] or 0 
                        for p in plans
                    ),
                    'is_delayed': is_delayed,
                    'confidence_level': confidence,
                    'is_next_day': is_next_day,
                    'error_message': ''
                }
            )
            
            result = {
                'success': True,
                'completion_time': completion_time,
                'is_delayed': is_delayed,
                'is_next_day': is_next_day,
                'current_rate': float(current_rate) if current_rate else 0,
                'confidence': confidence,
                'total_planned': sum(p.quantity for p in plans),
                'total_actual': sum(
                    p.results.aggregate(total=Sum('quantity'))['total'] or 0 
                    for p in plans
                )
            }
            
            self.logger.info(f"終了予測計算完了: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"終了予測計算エラー line={line_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': '計算エラー'
            }
    
    def _get_current_production_info(self, plans, now) -> Tuple[Optional[object], Decimal]:
        """現在生産中機種の判定と生産速度計算（修正版）"""
        # 直近の実績から現在生産中の機種を特定
        recent_results = Result.objects.filter(
            plan__in=plans,
            timestamp__gte=now - timedelta(hours=2)  # 2時間以内の実績
        ).order_by('-timestamp').select_related('plan', 'plan__part')
        
        if not recent_results.exists():
            return None, Decimal('0')
        
        # 最新の実績から現在の機種を判定
        latest_result = recent_results.first()
        current_plan = latest_result.plan
        
        # 計画数に達しているかチェック
        actual_qty = current_plan.results.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        if actual_qty >= current_plan.quantity:
            return None, Decimal('0')  # 現在の機種は完了済み
        
        # 修正：現在の機種の連続生産時間が30分以上かチェック
        current_part_results = Result.objects.filter(
            plan__part=current_plan.part,
            plan__line=current_plan.line,
            plan__date=current_plan.date
        ).order_by('-timestamp')
        
        if current_part_results.exists():
            # 連続生産時間を計算（最新から遡って同一機種の連続期間）
            continuous_start_time = self._find_continuous_production_start(
                current_part_results, now
            )
            production_duration = now - continuous_start_time
            
            if production_duration >= timedelta(minutes=30):
                # 30分以上連続生産：実績ベースの速度計算
                recent_30min = current_part_results.filter(
                    timestamp__gte=now - timedelta(minutes=30)
                )
                
                if recent_30min.exists():
                    total_qty = recent_30min.aggregate(
                        total=Sum('quantity')
                    )['total'] or 0
                    current_rate = Decimal(str((total_qty / 30) * 60))  # 時間当たりに換算
                    
                    # 異常値チェック
                    planned_pph = current_plan.planned_pph or 10
                    if current_rate <= 0 or current_rate > planned_pph * 3:
                        current_rate = Decimal(str(planned_pph))  # 計画値にフォールバック
                else:
                    current_rate = Decimal(str(current_plan.planned_pph or 10))
            else:
                # 30分未満の連続生産：計画ベース
                current_rate = Decimal(str(current_plan.planned_pph or 10))
        else:
            current_rate = Decimal(str(current_plan.planned_pph or 10))
        
        return current_plan.part, current_rate
    
    def _find_continuous_production_start(self, results, current_time) -> datetime:
        """連続生産開始時刻を見つける"""
        if not results.exists():
            return current_time
        
        # 最新の実績から遡って、5分以上の間隔がある時点を探す
        prev_time = current_time
        continuous_start = current_time
        
        for result in results:
            time_gap = prev_time - result.timestamp
            if time_gap > timedelta(minutes=5):  # 5分以上の間隔で生産中断と判定
                break
            continuous_start = result.timestamp
            prev_time = result.timestamp
        
        return continuous_start
    
    def _estimate_completion_time_with_breaks(
        self, start_time: datetime, remaining_work: List[Dict], work_calendar
    ) -> Tuple[Optional[time], int]:
        """休憩時間を考慮した完了時刻推定"""
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
                break_start = datetime.combine(current_time.date(), break_start_time)
                break_end = datetime.combine(current_time.date(), break_end_time)
                
                # 休憩終了時刻が開始時刻より早い場合（日またぎ）
                if break_end_time < break_start_time:
                    break_end = break_end + timedelta(days=1)
                
                # 現在時刻が休憩開始時刻より前の日の場合、翌日の休憩とする
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