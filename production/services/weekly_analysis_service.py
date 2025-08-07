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
                judgment='OK'
            ).aggregate(
                ok_quantity=Sum('total_quantity')
            )
            
            ng_stats = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date__range=(start_date, end_date),
                judgment='NG'
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