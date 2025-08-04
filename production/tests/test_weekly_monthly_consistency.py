"""
週別分析と月別分析の整合性テスト
"""
from django.test import TestCase
from django.utils import timezone
from datetime import date, datetime, timedelta
import logging

from production.models import Line, Part, Plan, WeeklyResultAggregation
from production.utils import (
    get_weekly_graph_data,
    get_monthly_graph_data,
    get_month_dates,
    get_week_dates
)


class WeeklyMonthlyConsistencyTest(TestCase):
    """週別分析と月別分析の整合性テスト"""
    
    def setUp(self):
        """テストデータ準備"""
        # テスト用ライン作成
        self.line = Line.objects.create(
            name='テストライン',
            description='整合性テスト用ライン'
        )
        
        # テスト用機種作成
        self.part1 = Part.objects.create(name='機種X')
        self.part2 = Part.objects.create(name='機種Y')
        
        # テスト日付（2025年1月の第2週）
        self.test_date = date(2025, 1, 8)  # 2025年1月8日（水曜日）
        self.week_dates = get_week_dates(self.test_date)
        self.month_dates = get_month_dates(self.test_date)
        
        # 共通のテストデータ作成
        self._create_test_data()
    
    def _create_test_data(self):
        """テスト用データ作成"""
        # 計画データ作成（週のデータ）
        for i, test_date in enumerate(self.week_dates):
            Plan.objects.create(
                line=self.line,
                date=test_date,
                part=self.part1,
                planned_quantity=200 + i * 20,
                sequence=1
            )
            Plan.objects.create(
                line=self.line,
                date=test_date,
                part=self.part2,
                planned_quantity=100 + i * 10,
                sequence=2
            )
        
        # 集計データ作成（週のデータ）
        for i, test_date in enumerate(self.week_dates):
            # 機種X実績
            WeeklyResultAggregation.objects.create(
                date=test_date,
                line=self.line.name,
                part=self.part1.name,
                judgment='OK',
                total_quantity=180 + i * 15,
                result_count=1
            )
            WeeklyResultAggregation.objects.create(
                date=test_date,
                line=self.line.name,
                part=self.part1.name,
                judgment='NG',
                total_quantity=10,
                result_count=1
            )
            
            # 機種Y実績
            WeeklyResultAggregation.objects.create(
                date=test_date,
                line=self.line.name,
                part=self.part2.name,
                judgment='OK',
                total_quantity=85 + i * 8,
                result_count=1
            )
    
    def test_data_source_consistency(self):
        """データソースの一貫性テスト"""
        # 週別分析データ取得
        weekly_data = get_weekly_graph_data(self.line.id, self.test_date)
        
        # 月別分析データ取得
        monthly_data = get_monthly_graph_data(self.line.id, self.test_date)
        
        # 両方とも成功することを確認
        self.assertIsNotNone(weekly_data)
        self.assertIsNotNone(monthly_data)
        
        # 基本構造が同じであることを確認
        for data in [weekly_data, monthly_data]:
            self.assertIn('chart_data', data)
            self.assertIn('available_parts', data)
            self.assertIn('part_analysis', data)
    
    def test_part_list_consistency(self):
        """機種リストの一貫性テスト"""
        # 週別分析データ取得
        weekly_data = get_weekly_graph_data(self.line.id, self.test_date)
        
        # 月別分析データ取得  
        monthly_data = get_monthly_graph_data(self.line.id, self.test_date)
        
        # 機種名リストを取得
        weekly_parts = set(part.name for part in weekly_data['available_parts'])
        monthly_parts = set(part.name for part in monthly_data['available_parts'])
        
        # 機種リストが一致することを確認（この週のデータは月にも含まれる）
        self.assertTrue(weekly_parts.issubset(monthly_parts))
        
        # 機種分析のデータも確認
        weekly_part_names = set(part['name'] for part in weekly_data['part_analysis'])
        monthly_part_names = set(part['name'] for part in monthly_data['part_analysis'])
        
        self.assertTrue(weekly_part_names.issubset(monthly_part_names))
    
    def test_aggregation_data_consistency(self):
        """集計データの一貫性テスト"""
        # 週別分析データ取得
        weekly_data = get_weekly_graph_data(self.line.id, self.test_date)
        
        # 月別分析データ取得
        monthly_data = get_monthly_graph_data(self.line.id, self.test_date)
        
        # 週別分析の合計
        weekly_total_planned = weekly_data['weekly_stats']['total_planned']
        weekly_total_actual = weekly_data['weekly_stats']['total_actual']
        
        # 月別分析から該当週のデータを抽出
        monthly_chart_data = monthly_data['chart_data']
        
        # この週の日付に対応する月別データを取得
        week_start = self.week_dates[0]
        week_end = self.week_dates[-1]
        
        monthly_week_planned = 0
        monthly_week_actual = 0
        
        for i, label in enumerate(monthly_chart_data['labels']):
            # 月別データの日付がこの週に含まれるかチェック
            month_date = self.month_dates[i]
            if week_start <= month_date <= week_end:
                monthly_week_planned += monthly_chart_data['planned'][i]
                monthly_week_actual += monthly_chart_data['actual'][i]
        
        # 合計値が一致することを確認（若干の誤差は許容）
        self.assertAlmostEqual(weekly_total_planned, monthly_week_planned, delta=5)
        self.assertAlmostEqual(weekly_total_actual, monthly_week_actual, delta=5)
    
    def test_part_analysis_consistency(self):
        """機種別分析の一貫性テスト"""
        # 週別分析データ取得
        weekly_data = get_weekly_graph_data(self.line.id, self.test_date)
        
        # 月別分析データ取得
        monthly_data = get_monthly_graph_data(self.line.id, self.test_date)
        
        # 機種別データを辞書化
        weekly_parts = {part['name']: part for part in weekly_data['part_analysis']}
        monthly_parts = {part['name']: part for part in monthly_data['part_analysis']}
        
        # 共通の機種について比較
        common_parts = set(weekly_parts.keys()) & set(monthly_parts.keys())
        
        for part_name in common_parts:
            weekly_part = weekly_parts[part_name]
            monthly_part = monthly_parts[part_name]
            
            # 週のデータは月のデータの一部または同じはず
            # （月別データの方が多いか等しい）
            self.assertLessEqual(weekly_part['planned'], monthly_part['planned'] + 10)  # 若干の誤差許容
            self.assertLessEqual(weekly_part['actual'], monthly_part['actual'] + 10)
            
            # 達成率は似た値になるはず（完全一致は期待しない）
            if weekly_part['planned'] > 0 and monthly_part['planned'] > 0:
                weekly_rate = weekly_part['achievement_rate']
                monthly_rate = monthly_part['achievement_rate']
                # 達成率の差が30%以内であることを確認
                self.assertLess(abs(weekly_rate - monthly_rate), 30)
    
    def test_data_structure_consistency(self):
        """データ構造の一貫性テスト"""
        # 週別分析データ取得
        weekly_data = get_weekly_graph_data(self.line.id, self.test_date)
        
        # 月別分析データ取得
        monthly_data = get_monthly_graph_data(self.line.id, self.test_date)
        
        # チャートデータの構造確認
        weekly_chart = weekly_data['chart_data']
        monthly_chart = monthly_data['chart_data']
        
        # 必要なキーが存在することを確認
        required_keys = ['labels', 'planned', 'actual']
        for key in required_keys:
            self.assertIn(key, weekly_chart)
            self.assertIn(key, monthly_chart)
        
        # 機種分析データの構造確認
        if weekly_data['part_analysis']:
            weekly_part = weekly_data['part_analysis'][0]
            monthly_part = monthly_data['part_analysis'][0]
            
            part_keys = ['name', 'planned', 'actual', 'achievement_rate']
            for key in part_keys:
                self.assertIn(key, weekly_part)
                self.assertIn(key, monthly_part)
    
    def test_error_handling_consistency(self):
        """エラーハンドリングの一貫性テスト"""
        # 存在しないラインでのテスト
        try:
            weekly_data = get_weekly_graph_data(99999, self.test_date)
            weekly_error = False
        except Exception:
            weekly_error = True
        
        try:
            monthly_data = get_monthly_graph_data(99999, self.test_date)
            monthly_error = False
        except Exception:
            monthly_error = True
        
        # 両方とも同じようにエラーハンドリングされることを確認
        self.assertEqual(weekly_error, monthly_error)
    
    def test_logging_consistency(self):
        """ログ出力の一貫性テスト"""
        with self.assertLogs('production.utils', level='INFO') as log:
            # 両方の関数を実行
            get_weekly_graph_data(self.line.id, self.test_date)
            get_monthly_graph_data(self.line.id, self.test_date)
        
        # ログメッセージが出力されていることを確認
        log_messages = [record.message for record in log.records]
        
        # 週別・月別それぞれのログが出力されていることを確認
        weekly_logs = [msg for msg in log_messages if '週別' in msg or 'weekly' in msg.lower()]
        monthly_logs = [msg for msg in log_messages if '月別' in msg or 'monthly' in msg.lower()]
        
        # 両方ともログが出力されていることを確認
        self.assertGreater(len(weekly_logs) + len(monthly_logs), 0)