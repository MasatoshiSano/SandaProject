"""
週別分析パフォーマンス改善のためのサービスクラス
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from django.db import models, transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import Result, WeeklyResultAggregation, Line, WorkCalendar

logger = logging.getLogger(__name__)


class AggregationService:
    """実績データの集計処理を行うサービスクラス"""
    
    def __init__(self):
        self.logger = logger
    
    def _get_work_period_for_date(self, line_id: int, target_date: date) -> tuple[datetime, datetime]:
        """
        指定日の稼働期間を取得（work_start_time基準）
        
        Args:
            line_id: ライン ID
            target_date: 対象日
            
        Returns:
            tuple: (開始datetime, 終了datetime)
        """
        try:
            work_calendar = WorkCalendar.objects.get(line_id=line_id)
            work_start_time = work_calendar.work_start_time
        except WorkCalendar.DoesNotExist:
            work_start_time = time(8, 30)  # デフォルトの稼働開始時間
            self.logger.warning(f"ライン {line_id} のWorkCalendarが見つかりません。デフォルト時間 {work_start_time} を使用します。")
        
        # work_start_timeから次の日のwork_start_timeまでの期間
        start_datetime = datetime.combine(target_date, work_start_time)
        end_datetime = datetime.combine(target_date + timedelta(days=1), work_start_time)
        
        # タイムゾーンを考慮
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
        
        return start_datetime, end_datetime
    
    def _get_work_period_for_date_by_line_name(self, line_name: str, target_date: date) -> tuple[datetime, datetime]:
        """
        指定日の稼働期間を取得（ライン名から、work_start_time基準）
        
        Args:
            line_name: ライン名
            target_date: 対象日
            
        Returns:
            tuple: (開始datetime, 終了datetime)
        """
        try:
            line = Line.objects.get(name=line_name)
            return self._get_work_period_for_date(line.id, target_date)
        except Line.DoesNotExist:
            self.logger.warning(f"ライン '{line_name}' が見つかりません。カレンダー日で集計します。")
            # フォールバック: カレンダー日
            start_datetime = datetime.combine(target_date, time.min)
            end_datetime = datetime.combine(target_date, time.max)
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
            return start_datetime, end_datetime
    
    def aggregate_single_date(self, line_id: int, target_date: date) -> int:
        """
        指定日の実績データを集計してWeeklyResultAggregationテーブルに保存
        
        Args:
            line_id: ライン ID
            target_date: 集計対象日
            
        Returns:
            int: 集計されたレコード数
        """
        try:
            # ラインオブジェクトを取得
            line = Line.objects.get(id=line_id)
            line_name = line.name
            
            self.logger.info(f"単日集計開始: ライン={line_name}, 日付={target_date}")
            
            # 既存の集計データを削除
            deleted_count = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date=target_date
            ).delete()[0]
            
            if deleted_count > 0:
                self.logger.info(f"既存集計データを削除: {deleted_count}件")
            
            # 対象日の実績データを取得（work_start_time基準）
            start_datetime, end_datetime = self._get_work_period_for_date(line_id, target_date)
            self.logger.info(f"集計期間: {start_datetime} ～ {end_datetime}")
            
            # 実績データを機種・設備・判定別に集計
            results = Result.objects.filter(
                line=line_name,
                timestamp__range=(start_datetime, end_datetime)
            ).values(
                'machine', 'part', 'judgment'
            ).annotate(
                total_quantity=Sum('quantity'),
                result_count=Count('id')
            )
            
            # 集計データを保存
            aggregation_records = []
            for result in results:
                aggregation_records.append(
                    WeeklyResultAggregation(
                        date=target_date,
                        line=line_name,
                        machine=result['machine'] or '',
                        part=result['part'] or '',
                        judgment=result['judgment'],
                        total_quantity=result['total_quantity'] or 0,
                        result_count=result['result_count'] or 0
                    )
                )
            
            # バルクインサートで効率的に保存
            if aggregation_records:
                with transaction.atomic():
                    WeeklyResultAggregation.objects.bulk_create(
                        aggregation_records,
                        batch_size=1000
                    )
            
            created_count = len(aggregation_records)
            self.logger.info(f"単日集計完了: {created_count}件のレコードを作成")
            
            return created_count
            
        except Line.DoesNotExist:
            self.logger.error(f"ライン ID {line_id} が見つかりません")
            raise
        except Exception as e:
            self.logger.error(f"単日集計エラー: {e}")
            raise
    
    def aggregate_date_range(self, line_id: int, start_date: date, end_date: date) -> int:
        """
        指定期間の実績データを集計
        
        Args:
            line_id: ライン ID
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            int: 集計されたレコード数の合計
        """
        try:
            self.logger.info(f"期間集計開始: ライン ID={line_id}, 期間={start_date} - {end_date}")
            
            total_count = 0
            current_date = start_date
            
            while current_date <= end_date:
                count = self.aggregate_single_date(line_id, current_date)
                total_count += count
                current_date += timedelta(days=1)
            
            self.logger.info(f"期間集計完了: 合計{total_count}件のレコードを作成")
            return total_count
            
        except Exception as e:
            self.logger.error(f"期間集計エラー: {e}")
            raise
    
    def incremental_update(self, result_instance: Result) -> None:
        """
        単一の実績データ変更に対する増分更新
        
        Args:
            result_instance: 変更された Result インスタンス
        """
        try:
            if not result_instance.line or not result_instance.part:
                self.logger.warning("ライン名または機種名が空のため、集計をスキップします")
                return
            
            target_date = result_instance.timestamp.date()
            
            self.logger.info(
                f"増分更新: ライン={result_instance.line}, "
                f"日付={target_date}, 機種={result_instance.part}"
            )
            
            # トランザクションと排他制御で安全に更新
            with transaction.atomic():
                # 該当する集計レコードを検索または作成（SELECT FOR UPDATE で排他制御）
                try:
                    aggregation = WeeklyResultAggregation.objects.select_for_update().get(
                        date=target_date,
                        line=result_instance.line,
                        machine=result_instance.machine or '',
                        part=result_instance.part,
                        judgment=result_instance.judgment
                    )
                    created = False
                except WeeklyResultAggregation.DoesNotExist:
                    aggregation = WeeklyResultAggregation(
                        date=target_date,
                        line=result_instance.line,
                        machine=result_instance.machine or '',
                        part=result_instance.part,
                        judgment=result_instance.judgment,
                        total_quantity=0,
                        result_count=0
                    )
                    created = True
                
                # 該当日の実績データを再集計（work_start_time基準）
                start_datetime, end_datetime = self._get_work_period_for_date_by_line_name(result_instance.line, target_date)
                
                # 同じ条件の実績データを集計
                result_data = Result.objects.filter(
                    line=result_instance.line,
                    machine=result_instance.machine or '',
                    part=result_instance.part,
                    judgment=result_instance.judgment,
                    timestamp__range=(start_datetime, end_datetime)
                ).aggregate(
                    total_quantity=Sum('quantity'),
                    result_count=Count('id')
                )
                
                # 集計データを更新
                aggregation.total_quantity = result_data['total_quantity'] or 0
                aggregation.result_count = result_data['result_count'] or 0
                aggregation.save()
                
                action = "作成" if created else "更新"
                self.logger.info(f"増分更新完了: 集計レコードを{action}")
                
                # WebSocket通知を送信
                _send_aggregation_notification(result_instance, action)
            
        except Exception as e:
            self.logger.error(f"増分更新エラー: {e}")
            raise
    
    def incremental_delete(self, result_instance: Result) -> None:
        """
        実績データ削除時の増分更新
        
        Args:
            result_instance: 削除された Result インスタンス
        """
        try:
            if not result_instance.line or not result_instance.part:
                self.logger.warning("ライン名または機種名が空のため、集計削除をスキップします")
                return
            
            target_date = result_instance.timestamp.date()
            
            self.logger.info(
                f"増分削除: ライン={result_instance.line}, "
                f"日付={target_date}, 機種={result_instance.part}"
            )
            
            with transaction.atomic():
                try:
                    # 該当する集計レコードを取得
                    aggregation = WeeklyResultAggregation.objects.select_for_update().get(
                        date=target_date,
                        line=result_instance.line,
                        machine=result_instance.machine or '',
                        part=result_instance.part,
                        judgment=result_instance.judgment
                    )
                    
                    # 該当日の残りの実績データを再集計（work_start_time基準）
                    start_datetime, end_datetime = self._get_work_period_for_date_by_line_name(result_instance.line, target_date)
                    
                    result_data = Result.objects.filter(
                        line=result_instance.line,
                        machine=result_instance.machine or '',
                        part=result_instance.part,
                        judgment=result_instance.judgment,
                        timestamp__range=(start_datetime, end_datetime)
                    ).aggregate(
                        total_quantity=Sum('quantity'),
                        result_count=Count('id')
                    )
                    
                    # データが残っている場合は更新、なければ削除
                    if result_data['result_count'] and result_data['result_count'] > 0:
                        aggregation.total_quantity = result_data['total_quantity'] or 0
                        aggregation.result_count = result_data['result_count'] or 0
                        aggregation.save()
                        self.logger.info("増分削除完了: 集計レコードを更新")
                    else:
                        aggregation.delete()
                        self.logger.info("増分削除完了: 集計レコードを削除")
                        
                except WeeklyResultAggregation.DoesNotExist:
                    self.logger.warning("削除対象の集計レコードが見つかりません")
            
        except Exception as e:
            self.logger.error(f"増分削除エラー: {e}")
            raise
    
    def validate_aggregation(self, line_id: int, target_date: date) -> bool:
        """
        集計データの整合性を検証
        
        Args:
            line_id: ライン ID
            target_date: 検証対象日
            
        Returns:
            bool: 整合性が取れている場合 True
        """
        try:
            line = Line.objects.get(id=line_id)
            line_name = line.name
            
            self.logger.info(f"集計検証開始: ライン={line_name}, 日付={target_date}")
            
            # 元データの集計（work_start_time基準）
            start_datetime, end_datetime = self._get_work_period_for_date(line_id, target_date)
            
            source_data = Result.objects.filter(
                line=line_name,
                timestamp__range=(start_datetime, end_datetime)
            ).values(
                'machine', 'part', 'judgment'
            ).annotate(
                total_quantity=Sum('quantity'),
                result_count=Count('id')
            )
            
            # 集計テーブルのデータ
            aggregated_data = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date=target_date
            ).values(
                'machine', 'part', 'judgment', 'total_quantity', 'result_count'
            )
            
            # データを辞書に変換して比較
            source_dict = {}
            for item in source_data:
                key = (
                    item['machine'] or '',
                    item['part'] or '',
                    item['judgment']
                )
                source_dict[key] = {
                    'total_quantity': item['total_quantity'] or 0,
                    'result_count': item['result_count'] or 0
                }
            
            aggregated_dict = {}
            for item in aggregated_data:
                key = (
                    item['machine'] or '',
                    item['part'] or '',
                    item['judgment']
                )
                aggregated_dict[key] = {
                    'total_quantity': item['total_quantity'],
                    'result_count': item['result_count']
                }
            
            # 整合性チェック
            is_consistent = source_dict == aggregated_dict
            
            if is_consistent:
                self.logger.info("集計データの整合性OK")
            else:
                self.logger.warning("集計データの不整合を検出")
                self.logger.warning(f"元データ: {len(source_dict)}件")
                self.logger.warning(f"集計データ: {len(aggregated_dict)}件")
            
            return is_consistent
            
        except Line.DoesNotExist:
            self.logger.error(f"ライン ID {line_id} が見つかりません")
            return False
        except Exception as e:
            self.logger.error(f"集計検証エラー: {e}")
            return False
    
    def repair_aggregation(self, line_id: int, target_date: date) -> bool:
        """
        集計データの自動修復
        
        Args:
            line_id: ライン ID
            target_date: 修復対象日
            
        Returns:
            bool: 修復が成功した場合 True
        """
        try:
            self.logger.info(f"集計修復開始: ライン ID={line_id}, 日付={target_date}")
            
            # 検証を実行
            if self.validate_aggregation(line_id, target_date):
                self.logger.info("集計データは正常です。修復不要。")
                return True
            
            # 不整合が検出された場合、再集計を実行
            self.logger.info("不整合を検出。再集計を実行します。")
            count = self.aggregate_single_date(line_id, target_date)
            
            # 修復後の検証
            if self.validate_aggregation(line_id, target_date):
                self.logger.info(f"集計修復完了: {count}件のレコードを再作成")
                return True
            else:
                self.logger.error("修復後も不整合が残っています")
                return False
                
        except Exception as e:
            self.logger.error(f"集計修復エラー: {e}")
            return False
    
    def get_aggregation_summary(self, line_id: int, target_date: date) -> dict:
        """
        集計データのサマリー情報を取得
        
        Args:
            line_id: ライン ID
            target_date: 対象日
            
        Returns:
            dict: サマリー情報
        """
        try:
            line = Line.objects.get(id=line_id)
            line_name = line.name
            
            # 集計データの統計
            aggregations = WeeklyResultAggregation.objects.filter(
                line=line_name,
                date=target_date
            )
            
            total_records = aggregations.count()
            total_quantity = sum(agg.total_quantity for agg in aggregations)
            total_results = sum(agg.result_count for agg in aggregations)
            
            # 判定別統計
            ok_aggregations = aggregations.filter(judgment='OK')
            ng_aggregations = aggregations.filter(judgment='NG')
            
            ok_quantity = sum(agg.total_quantity for agg in ok_aggregations)
            ng_quantity = sum(agg.total_quantity for agg in ng_aggregations)
            
            # 機種別統計
            parts = aggregations.values('part').distinct()
            part_count = len(parts)
            
            # 設備別統計
            machines = aggregations.values('machine').distinct()
            machine_count = len([m for m in machines if m['machine']])
            
            return {
                'line_name': line_name,
                'date': target_date,
                'total_records': total_records,
                'total_quantity': total_quantity,
                'total_results': total_results,
                'ok_quantity': ok_quantity,
                'ng_quantity': ng_quantity,
                'part_count': part_count,
                'machine_count': machine_count,
                'is_consistent': self.validate_aggregation(line_id, target_date)
            }
            
        except Line.DoesNotExist:
            self.logger.error(f"ライン ID {line_id} が見つかりません")
            return {}
        except Exception as e:
            self.logger.error(f"サマリー取得エラー: {e}")
            return {}
    
    def detect_inconsistencies(self, line_id: int, start_date: date, end_date: date) -> list:
        """
        期間内の不整合を検出
        
        Args:
            line_id: ライン ID
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            list: 不整合が検出された日付のリスト
        """
        try:
            self.logger.info(f"不整合検出開始: ライン ID={line_id}, 期間={start_date} - {end_date}")
            
            inconsistent_dates = []
            current_date = start_date
            
            while current_date <= end_date:
                if not self.validate_aggregation(line_id, current_date):
                    inconsistent_dates.append(current_date)
                    self.logger.warning(f"不整合検出: {current_date}")
                
                current_date += timedelta(days=1)
            
            self.logger.info(f"不整合検出完了: {len(inconsistent_dates)}日で不整合を検出")
            return inconsistent_dates
            
        except Exception as e:
            self.logger.error(f"不整合検出エラー: {e}")
            return []
    
    def batch_repair(self, line_id: int, start_date: date, end_date: date) -> dict:
        """
        期間内の集計データを一括修復
        
        Args:
            line_id: ライン ID
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            dict: 修復結果のサマリー
        """
        try:
            self.logger.info(f"一括修復開始: ライン ID={line_id}, 期間={start_date} - {end_date}")
            
            # 不整合を検出
            inconsistent_dates = self.detect_inconsistencies(line_id, start_date, end_date)
            
            if not inconsistent_dates:
                self.logger.info("不整合は検出されませんでした")
                return {
                    'total_days': (end_date - start_date).days + 1,
                    'inconsistent_days': 0,
                    'repaired_days': 0,
                    'failed_days': 0,
                    'success_rate': 100.0
                }
            
            # 不整合のある日付を修復
            repaired_count = 0
            failed_count = 0
            
            for target_date in inconsistent_dates:
                if self.repair_aggregation(line_id, target_date):
                    repaired_count += 1
                else:
                    failed_count += 1
            
            total_days = (end_date - start_date).days + 1
            success_rate = (repaired_count / len(inconsistent_dates)) * 100 if inconsistent_dates else 100.0
            
            result = {
                'total_days': total_days,
                'inconsistent_days': len(inconsistent_dates),
                'repaired_days': repaired_count,
                'failed_days': failed_count,
                'success_rate': success_rate
            }
            
            self.logger.info(f"一括修復完了: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"一括修復エラー: {e}")
            return {
                'total_days': 0,
                'inconsistent_days': 0,
                'repaired_days': 0,
                'failed_days': 0,
                'success_rate': 0.0,
                'error': str(e)
            }


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

def _send_aggregation_notification(result_instance: Result, action: str) -> None:
    """集計更新のWebSocket通知を送信"""
    try:
        from .models import send_aggregation_status_notification, send_weekly_analysis_update
        
        # 集計状況の通知
        send_aggregation_status_notification('aggregation_updated', {
            'line_name': result_instance.line,
            'date': result_instance.timestamp.date().isoformat(),
            'action': action
        })
        
        # 週別分析の更新通知（該当週）
        target_date = result_instance.timestamp.date()
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        try:
            line = Line.objects.get(name=result_instance.line)
            send_weekly_analysis_update(line.id, week_start, week_end)
        except Line.DoesNotExist:
            logger.warning(f"ライン '{result_instance.line}' が見つかりません")
        
    except Exception as e:
        logger.error(f"WebSocket通知送信エラー: {e}")
        # 通知エラーは集計処理に影響させない