"""
週別分析サービス
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from django.db.models import Sum, Count
from ..models import WeeklyResultAggregation

logger = logging.getLogger(__name__)


class WeeklyAnalysisService:
    """集計テーブルを使用した高速な週別分析サービス"""
    
    def __init__(self):
        self.logger = logger
    
    def get_weekly_data(self, line_name: str, start_date: date, end_date: date) -> list:
        """
        週別分析データを集計テーブルから高速取得
        
        Args:
            line_name: ライン名
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            list: 週別分析データ
        """
        try:
            self.logger.info(f"週別データ取得開始: ライン={line_name}, 期間={start_date}-{end_date}")
            
            # 集計データを取得
            aggregations = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date__range=(start_date, end_date)
            ).values(
                'date', 'judgment'
            ).annotate(
                total_quantity=Sum('total_quantity'),
                total_count=Sum('result_count')
            ).order_by('date', 'judgment')
            
            return list(aggregations)
        
        except Exception as e:
            self.logger.error(f"週別データ取得エラー: {e}")
            return []
    
    def get_part_analysis(self, line_name: str, part_name: str, start_date: date, end_date: date) -> list:
        """
        機種別分析データを取得
        
        Args:
            line_name: ライン名
            part_name: 機種名
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            list: 機種別分析データ
        """
        try:
            self.logger.info(f"機種別分析開始: ライン={line_name}, 機種={part_name}, 期間={start_date}-{end_date}")
            
            # 集計データを取得
            aggregations = WeeklyResultAggregation.objects.filter(
                line=line_name,
                part=part_name,
                date__range=(start_date, end_date)
            ).values(
                'date', 'judgment'
            ).annotate(
                total_quantity=Sum('total_quantity'),
                total_count=Sum('result_count')
            ).order_by('date', 'judgment')
            
            return list(aggregations)
        
        except Exception as e:
            self.logger.error(f"機種別分析エラー: {e}")
            return []
    
    def get_performance_metrics(self, line_name: str, start_date: date, end_date: date) -> dict:
        """
        パフォーマンス指標を取得
        
        Args:
            line_name: ライン名
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            dict: パフォーマンス指標
        """
        try:
            self.logger.info(f"パフォーマンス指標取得開始: ライン={line_name}, 期間={start_date}-{end_date}")
            
            # 集計データから統計を計算
            stats = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date__range=(start_date, end_date)
            ).aggregate(
                total_quantity=Sum('total_quantity'),
                total_count=Sum('result_count')
            )
            
            # OK/NG別の統計を個別に取得
            ok_stats = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date__range=(start_date, end_date),
                judgment='1'  # OK判定
            ).aggregate(
                ok_quantity=Sum('total_quantity')
            )
            
            ng_stats = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date__range=(start_date, end_date),
                judgment='2'  # NG判定
            ).aggregate(
                ng_quantity=Sum('total_quantity')
            )
            
            # 指標を計算
            total_quantity = stats['total_quantity'] or 0
            ok_quantity = ok_stats['ok_quantity'] or 0
            ng_quantity = ng_stats['ng_quantity'] or 0
            
            metrics = {
                'total_quantity': total_quantity,
                'ok_quantity': ok_quantity,
                'ng_quantity': ng_quantity,
                'defect_rate': (ng_quantity / total_quantity * 100) if total_quantity > 0 else 0,
                'yield_rate': (ok_quantity / total_quantity * 100) if total_quantity > 0 else 0
            }
            
            return metrics
        
        except Exception as e:
            self.logger.error(f"パフォーマンス指標取得エラー: {e}")
            return {}
    
    def get_complete_weekly_data(self, line_id: int, date: date) -> dict:
        """
        完全な週別分析データを取得（WeeklyResultAggregationのみ使用）
        
        Args:
            line_id: ライン ID
            date: 基準日
            
        Returns:
            dict: 完全な週別グラフデータ
        """
        from datetime import timedelta
        from ..models import Line, Part, Plan, Machine
        from ..utils import get_week_dates
        
        try:
            # ライン取得
            line = Line.objects.get(id=line_id)
            line_name = line.name
            
            # カウント対象設備を取得
            count_target_machines = Machine.objects.filter(
                line_id=line_id,
                is_active=True,
                is_count_target=True
            )
            count_target_machine_names = [m.name for m in count_target_machines]
            
            if not count_target_machine_names:
                self.logger.warning(f"ライン {line_name} にカウント対象設備がありません")
                return self._get_empty_data_structure()
            
            # 週の日付を取得
            week_dates = get_week_dates(date)
            week_start = week_dates[0]
            week_end = week_dates[-1]
            
            self.logger.info(f"完全週別データ取得: ライン={line_name}, 週={week_start}-{week_end}")
            self.logger.info(f"カウント対象設備: {count_target_machine_names}")
            
            # 日別データを構築
            daily_data = []
            total_planned = 0
            total_actual = 0
            
            for day in week_dates:
                # その日の計画数を取得
                day_plans = Plan.objects.filter(line=line, date=day)
                planned = sum(plan.planned_quantity for plan in day_plans)
                
                # その日の実績数を集計テーブルから取得（OK判定のみ、カウント対象設備のみ）
                day_aggregations = WeeklyResultAggregation.objects.filter(
                    line=line_name,
                    date=day,
                    judgment='1',  # OK判定のみ
                    machine__in=count_target_machine_names  # カウント対象設備のみ
                )
                actual = sum(agg.total_quantity for agg in day_aggregations)
                
                achievement_rate = (actual / planned * 100) if planned > 0 else 0
                
                daily_data.append({
                    'date': day.strftime('%Y-%m-%d'),
                    'date_display': day.strftime('%m/%d(%a)'),
                    'planned': planned,
                    'actual': actual,
                    'achievement_rate': achievement_rate,
                })
                
                total_planned += planned
                total_actual += actual
            
            # 累計データ計算
            cumulative_planned = []
            cumulative_actual = []
            planned_sum = 0
            actual_sum = 0
            
            for d in daily_data:
                planned_sum += d['planned']
                actual_sum += d['actual']
                cumulative_planned.append(planned_sum)
                cumulative_actual.append(actual_sum)
            
            # チャートデータ生成
            chart_data = {
                'labels': [d['date_display'] for d in daily_data],
                'planned': [d['planned'] for d in daily_data],
                'actual': [d['actual'] for d in daily_data],
                'cumulative_planned': cumulative_planned,
                'cumulative_actual': cumulative_actual,
            }
            
            # 週間統計
            achievement_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
            working_days = sum(1 for d in daily_data if d['planned'] > 0 or d['actual'] > 0)
            
            weekly_stats = {
                'total_planned': total_planned,
                'total_actual': total_actual,
                'achievement_rate': achievement_rate,
                'working_days': working_days,
                'total_days': 7,
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
            }
            
            # 利用可能機種を取得（カウント対象設備のみ）
            available_part_names = list(WeeklyResultAggregation.objects.filter(
                line=line_name,
                date__in=week_dates,
                machine__in=count_target_machine_names  # カウント対象設備のみ
            ).values_list('part', flat=True).distinct())
            
            available_parts = Part.objects.filter(name__in=available_part_names) if available_part_names else Part.objects.none()
            
            # 機種別分析
            part_analysis = []
            for part in available_parts:
                part_data = self.get_part_analysis(line_name, part.name, week_start, week_end)
                if part_data:
                    part_total_ok = sum(d.get('total_quantity', 0) for d in part_data if d.get('judgment') == '1')
                    part_total_ng = sum(d.get('total_quantity', 0) for d in part_data if d.get('judgment') == '2')
                    part_analysis.append({
                        'part': part,
                        'ok_quantity': part_total_ok,
                        'ng_quantity': part_total_ng,
                        'total_quantity': part_total_ok + part_total_ng,
                        'quality_rate': (part_total_ok / (part_total_ok + part_total_ng) * 100) if (part_total_ok + part_total_ng) > 0 else 0
                    })
            
            return {
                'chart_data': chart_data,
                'weekly_stats': weekly_stats,
                'available_parts': available_parts,
                'part_analysis': part_analysis,
                'daily_data': daily_data,
            }
            
        except Line.DoesNotExist:
            self.logger.error(f"ライン ID {line_id} が見つかりません")
            return self._get_empty_data_structure()
        except Exception as e:
            self.logger.error(f"完全週別データ取得エラー: {e}")
            return self._get_empty_data_structure()
    
    def get_complete_monthly_data(self, line_id: int, year: int, month: int) -> dict:
        """
        完全な月別分析データを取得（WeeklyResultAggregationのみ使用）
        
        Args:
            line_id: ライン ID
            year: 年
            month: 月
            
        Returns:
            dict: 完全な月別グラフデータ
        """
        from datetime import datetime
        from calendar import monthrange
        from ..models import Line, Part, Plan, Machine
        
        try:
            # ライン取得
            line = Line.objects.get(id=line_id)
            line_name = line.name
            
            # カウント対象設備を取得
            count_target_machines = Machine.objects.filter(
                line_id=line_id,
                is_active=True,
                is_count_target=True
            )
            count_target_machine_names = [m.name for m in count_target_machines]
            
            if not count_target_machine_names:
                self.logger.warning(f"ライン {line_name} にカウント対象設備がありません")
                return self._get_empty_monthly_data_structure(year, month)
            
            # 月の日付範囲を取得
            first_day = date(year, month, 1)
            last_day_num = monthrange(year, month)[1]
            last_day = date(year, month, last_day_num)
            
            self.logger.info(f"完全月別データ取得: ライン={line_name}, 月={year}-{month:02d}")
            self.logger.info(f"カウント対象設備: {count_target_machine_names}")
            
            # 日別データを構築
            daily_data = []
            total_planned = 0
            total_actual = 0
            
            current_day = first_day
            while current_day <= last_day:
                # その日の計画数を取得
                day_plans = Plan.objects.filter(line=line, date=current_day)
                planned = sum(plan.planned_quantity for plan in day_plans)
                
                # その日の実績数を集計テーブルから取得（OK判定のみ、カウント対象設備のみ）
                day_aggregations = WeeklyResultAggregation.objects.filter(
                    line=line_name,
                    date=current_day,
                    judgment='1',  # OK判定のみ
                    machine__in=count_target_machine_names  # カウント対象設備のみ
                )
                actual = sum(agg.total_quantity for agg in day_aggregations)
                
                achievement_rate = (actual / planned * 100) if planned > 0 else 0
                
                daily_data.append({
                    'date': current_day.strftime('%Y-%m-%d'),
                    'date_display': current_day.strftime('%m/%d'),
                    'planned': planned,
                    'actual': actual,
                    'achievement_rate': achievement_rate,
                })
                
                total_planned += planned
                total_actual += actual
                current_day += timedelta(days=1)
            
            # チャートデータ生成
            chart_data = {
                'labels': [d['date_display'] for d in daily_data],
                'planned': [d['planned'] for d in daily_data],
                'actual': [d['actual'] for d in daily_data],
            }
            
            # 月間統計
            achievement_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
            working_days = sum(1 for d in daily_data if d['planned'] > 0 or d['actual'] > 0)
            
            monthly_stats = {
                'total_planned': total_planned,
                'total_actual': total_actual,
                'achievement_rate': achievement_rate,
                'working_days': working_days,
                'total_days': last_day_num,
                'year': year,
                'month': month,
            }
            
            # 利用可能機種を取得（カウント対象設備のみ）
            available_part_names = list(WeeklyResultAggregation.objects.filter(
                line=line_name,
                date__range=(first_day, last_day),
                machine__in=count_target_machine_names  # カウント対象設備のみ
            ).values_list('part', flat=True).distinct())
            
            available_parts = Part.objects.filter(name__in=available_part_names) if available_part_names else Part.objects.none()
            
            return {
                'chart_data': chart_data,
                'monthly_stats': monthly_stats,
                'available_parts': available_parts,
                'daily_data': daily_data,
            }
            
        except Line.DoesNotExist:
            self.logger.error(f"ライン ID {line_id} が見つかりません")
            return self._get_empty_monthly_data_structure(year, month)
        except Exception as e:
            self.logger.error(f"完全月別データ取得エラー: {e}")
            return self._get_empty_monthly_data_structure(year, month)
    
    def _get_empty_data_structure(self) -> dict:
        """空のデータ構造を返す"""
        from ..models import Part
        return {
            'chart_data': {
                'labels': [],
                'planned': [],
                'actual': [],
                'cumulative_planned': [],
                'cumulative_actual': [],
            },
            'weekly_stats': {
                'total_planned': 0,
                'total_actual': 0,
                'achievement_rate': 0,
                'working_days': 0,
                'total_days': 7,
            },
            'available_parts': Part.objects.none(),
            'part_analysis': [],
            'daily_data': [],
        }
    
    def _get_empty_monthly_data_structure(self, year: int, month: int) -> dict:
        """空の月別データ構造を返す"""
        from ..models import Part
        from calendar import monthrange
        return {
            'chart_data': {
                'labels': [],
                'planned': [],
                'actual': [],
            },
            'monthly_stats': {
                'total_planned': 0,
                'total_actual': 0,
                'achievement_rate': 0,
                'working_days': 0,
                'total_days': monthrange(year, month)[1],
                'year': year,
                'month': month,
            },
            'available_parts': Part.objects.none(),
            'daily_data': [],
        }