"""
月別分析機能のテストケース
"""
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta
import logging

from production.models import Line, Part, Plan, WeeklyResultAggregation
from production.utils import (
    _get_monthly_data_from_aggregation,
    _calculate_monthly_part_analysis,
    get_monthly_graph_data,
    get_month_dates
)


class MonthlyAnalysisTestCase(TestCase):
    """月別分析機能のテストケース"""
    
    def setUp(self):
        """テストデータ準備"""
        # テスト用ライン作成
        self.line = Line.objects.create(
            name='テストライン1',
            description='テスト用ライン'
        )
        
        # テスト用機種作成
        self.part1 = Part.objects.create(name='機種A')
        self.part2 = Part.objects.create(name='機種B')
        
        # テスト日付
        self.test_date = date(2025, 1, 15)  # 2025年1月の中旬
        self.month_dates = get_month_dates(self.test_date)
        
        # テスト用計画データ作成
        for i, test_date in enumerate(self.month_dates[:10]):  # 最初の10日分
            Plan.objects.create(
                line=self.line,
                date=test_date,
                part=self.part1,
                planned_quantity=100 + i * 10,
                sequence=1
            )
            if i % 2 == 0:  # 偶数日のみ機種Bの計画も作成
                Plan.objects.create(
                    line=self.line,
                    date=test_date,
                    part=self.part2,
                    planned_quantity=50 + i * 5,
                    sequence=2
                )
        
        # テスト用集計データ作成
        for i, test_date in enumerate(self.month_dates[:10]):
            # 機種A実績
            WeeklyResultAggregation.objects.create(
                date=test_date,
                line=self.line.name,
                part=self.part1.name,
                judgment='OK',
                total_quantity=80 + i * 8,
                result_count=1
            )
            # NG実績も少し作成
            WeeklyResultAggregation.objects.create(
                date=test_date,
                line=self.line.name,
                part=self.part1.name,
                judgment='NG',
                total_quantity=5,
                result_count=1
            )
            
            if i % 2 == 0:  # 偶数日のみ機種B実績
                WeeklyResultAggregation.objects.create(
                    date=test_date,
                    line=self.line.name,
                    part=self.part2.name,
                    judgment='OK',
                    total_quantity=40 + i * 4,
                    result_count=1
                )


class GetMonthlyDataFromAggregationTest(MonthlyAnalysisTestCase):
    """_get_monthly_data_from_aggregation関数のテスト"""
    
    def test_normal_case(self):
        """正常ケース：標準的な月データの取得"""
        result = _get_monthly_data_from_aggregation(self.line.id, self.test_date)
        
        # 基本構造チェック
        self.assertIn('monthly_data', result)
        self.assertIn('monthly_stats', result)
        self.assertIn('line_name', result)
        self.assertIn('month_dates', result)
        
        # データ内容チェック
        monthly_data = result['monthly_data']
        self.assertEqual(len(monthly_data), len(self.month_dates))
        
        # 最初の日のデータチェック
        first_day_data = monthly_data[0]
        self.assertIn('date', first_day_data)
        self.assertIn('planned', first_day_data)
        self.assertIn('actual', first_day_data)
        self.assertIn('achievement_rate', first_day_data)
        
        # 統計データチェック
        monthly_stats = result['monthly_stats']
        self.assertGreater(monthly_stats['total_planned'], 0)
        self.assertGreater(monthly_stats['total_actual'], 0)
        self.assertGreaterEqual(monthly_stats['achievement_rate'], 0)
    
    def test_no_data_case(self):
        """エッジケース：データが存在しない月"""
        # 未来の日付で実行
        future_date = date(2030, 12, 15)
        result = _get_monthly_data_from_aggregation(self.line.id, future_date)
        
        # 基本構造は維持されている
        self.assertIn('monthly_data', result)
        self.assertIn('monthly_stats', result)
        
        # データは0
        monthly_stats = result['monthly_stats']
        self.assertEqual(monthly_stats['total_planned'], 0)
        self.assertEqual(monthly_stats['total_actual'], 0)
        self.assertEqual(monthly_stats['achievement_rate'], 0)
    
    def test_invalid_line_id(self):
        """エラーケース：存在しないライン"""
        with self.assertRaises(Line.DoesNotExist):
            _get_monthly_data_from_aggregation(99999, self.test_date)
    
    def test_logging(self):
        """ログ出力のテスト"""
        with self.assertLogs('production.utils', level='INFO') as log:
            _get_monthly_data_from_aggregation(self.line.id, self.test_date)
            
        # ログメッセージが出力されているかチェック
        self.assertTrue(any('月別データ取得開始' in message for message in log.output))
        self.assertTrue(any('月別データ取得完了' in message for message in log.output))


class CalculateMonthlyPartAnalysisTest(MonthlyAnalysisTestCase):
    """_calculate_monthly_part_analysis関数のテスト"""
    
    def test_normal_case(self):
        """正常ケース：機種別分析の計算"""
        result = _calculate_monthly_part_analysis(self.line.name, self.month_dates)
        
        # 基本構造チェック
        self.assertIn('available_parts', result)
        self.assertIn('part_analysis', result)
        
        # 機種データチェック
        part_analysis = result['part_analysis']
        self.assertGreater(len(part_analysis), 0)
        
        # 最初の機種データの構造チェック
        first_part = part_analysis[0]
        self.assertIn('name', first_part)
        self.assertIn('planned', first_part)
        self.assertIn('actual', first_part)
        self.assertIn('achievement_rate', first_part)
        self.assertIn('working_days', first_part)
        self.assertIn('average_pph', first_part)
        self.assertIn('color', first_part)
        
        # データの妥当性チェック
        self.assertGreater(first_part['planned'], 0)
        self.assertGreater(first_part['actual'], 0)
        self.assertGreaterEqual(first_part['achievement_rate'], 0)
    
    def test_no_parts_case(self):
        """エッジケース：機種データが存在しない"""
        # 存在しないラインで実行
        result = _calculate_monthly_part_analysis('存在しないライン', self.month_dates)
        
        # 空のリストが返される
        self.assertEqual(len(result['part_analysis']), 0)
        self.assertEqual(result['available_parts'].count(), 0)


class GetMonthlyGraphDataTest(MonthlyAnalysisTestCase):
    """get_monthly_graph_data関数のテスト"""
    
    def test_normal_case(self):
        """正常ケース：月別グラフデータの取得"""
        result = get_monthly_graph_data(self.line.id, self.test_date)
        
        # 全必要キーが存在するかチェック
        required_keys = [
            'chart_data', 'monthly_stats', 'calendar_data',
            'weekly_summary', 'available_parts', 'part_analysis'
        ]
        for key in required_keys:
            self.assertIn(key, result)
        
        # チャートデータの構造チェック
        chart_data = result['chart_data']
        self.assertIn('labels', chart_data)
        self.assertIn('planned', chart_data)
        self.assertIn('actual', chart_data)
        self.assertIn('cumulative_planned', chart_data)
        self.assertIn('cumulative_actual', chart_data)
        
        # データ件数チェック
        self.assertEqual(len(chart_data['labels']), len(self.month_dates))
        self.assertEqual(len(chart_data['planned']), len(self.month_dates))
        self.assertEqual(len(chart_data['actual']), len(self.month_dates))
        
        # 週別サマリーのチェック
        weekly_summary = result['weekly_summary']
        self.assertGreater(len(weekly_summary), 0)
        
        # 最初の週データの構造チェック
        first_week = weekly_summary[0]
        week_keys = [
            'week_number', 'start_date', 'end_date', 'working_days',
            'planned_quantity', 'actual_quantity', 'achievement_rate',
            'average_pph', 'part_count'
        ]
        for key in week_keys:
            self.assertIn(key, first_week)
    
    @patch('production.utils._get_monthly_data_from_aggregation')
    def test_fallback_on_error(self, mock_get_data):
        """エラー時のフォールバック動作テスト"""
        # 新しい関数でエラーを発生させる
        mock_get_data.side_effect = Exception("Test error")
        
        with self.assertLogs('production.utils', level='ERROR') as log:
            result = get_monthly_graph_data(self.line.id, self.test_date)
            
        # エラーログが出力されているかチェック
        self.assertTrue(any('月別グラフデータ取得エラー' in message for message in log.output))
        self.assertTrue(any('フォールバック' in message for message in log.output))
        
        # フォールバック結果でも基本構造は維持されている
        self.assertIn('chart_data', result)
        self.assertIn('monthly_stats', result)
    
    def test_cumulative_calculation(self):
        """累計データ計算の正確性テスト"""
        result = get_monthly_graph_data(self.line.id, self.test_date)
        
        chart_data = result['chart_data']
        planned = chart_data['planned']
        actual = chart_data['actual']
        cumulative_planned = chart_data['cumulative_planned']
        cumulative_actual = chart_data['cumulative_actual']
        
        # 累計計算の正確性をチェック
        expected_cumulative_planned = []
        expected_cumulative_actual = []
        planned_sum = 0
        actual_sum = 0
        
        for p, a in zip(planned, actual):
            planned_sum += p
            actual_sum += a
            expected_cumulative_planned.append(planned_sum)
            expected_cumulative_actual.append(actual_sum)
        
        self.assertEqual(cumulative_planned, expected_cumulative_planned)
        self.assertEqual(cumulative_actual, expected_cumulative_actual)


class PerformanceTest(MonthlyAnalysisTestCase):
    """性能テスト"""
    
    def test_query_count(self):
        """クエリ実行回数のテスト"""
        with self.assertNumQueries(10):  # 期待されるクエリ数（調整が必要な場合あり）
            result = get_monthly_graph_data(self.line.id, self.test_date)
    
    def test_execution_time(self):
        """実行時間のテスト"""
        import time
        
        # 実行時間を測定
        start_time = time.time()
        result = get_monthly_graph_data(self.line.id, self.test_date)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # 1秒以内で完了することを期待（要調整）
        self.assertLess(execution_time, 1.0)
        
        # ログに実行時間を記録
        print(f"月別分析実行時間: {execution_time:.3f}秒")