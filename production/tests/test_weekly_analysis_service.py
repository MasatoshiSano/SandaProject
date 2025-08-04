"""
WeeklyAnalysisService のテスト
"""

from datetime import date, datetime, time, timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from production.models import Line, WeeklyResultAggregation
from production.services import WeeklyAnalysisService


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    DATABASE_ROUTERS=[]  # ルーターを無効化
)
class TestWeeklyAnalysisService(TestCase):
    """WeeklyAnalysisService のテストクラス"""
    
    def setUp(self):
        """テスト用データの準備"""
        self.service = WeeklyAnalysisService()
        
        # テスト用ライン作成
        self.line = Line.objects.create(
            name="テストライン1",
            description="テスト用ライン"
        )
        
        # テスト用日付（2025年1月15日 = 水曜日）
        self.test_date = date(2025, 1, 15)
        
        # 週の開始日（月曜日）を計算
        self.week_start = self.test_date - timedelta(days=self.test_date.weekday())
        self.week_dates = [self.week_start + timedelta(days=i) for i in range(7)]
        
        # テスト用集計データを作成
        self._create_test_aggregation_data()
    
    def _create_test_aggregation_data(self):
        """テスト用の集計データを作成"""
        # 月曜日のデータ
        WeeklyResultAggregation.objects.create(
            date=self.week_dates[0],
            line=self.line.name,
            machine="機械A",
            part="製品X",
            judgment="OK",
            total_quantity=100,
            result_count=10
        )
        
        WeeklyResultAggregation.objects.create(
            date=self.week_dates[0],
            line=self.line.name,
            machine="機械A",
            part="製品X",
            judgment="NG",
            total_quantity=5,
            result_count=1
        )
        
        # 火曜日のデータ
        WeeklyResultAggregation.objects.create(
            date=self.week_dates[1],
            line=self.line.name,
            machine="機械B",
            part="製品Y",
            judgment="OK",
            total_quantity=80,
            result_count=8
        )
        
        # 水曜日のデータ（test_date）
        WeeklyResultAggregation.objects.create(
            date=self.week_dates[2],
            line=self.line.name,
            machine="機械A",
            part="製品X",
            judgment="OK",
            total_quantity=120,
            result_count=12
        )
    
    def test_service_creation(self):
        """WeeklyAnalysisService の作成テスト"""
        service = WeeklyAnalysisService()
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.logger)
    
    def test_get_weekly_data_structure(self):
        """週別データ取得の構造テスト"""
        start_date = self.week_start
        end_date = self.week_start + timedelta(days=6)
        
        result = self.service.get_weekly_data(self.line.name, start_date, end_date)
        
        # 結果がリストであることを確認
        self.assertIsInstance(result, list)
        
        # データが存在する場合の構造をチェック
        if result:
            first_item = result[0]
            self.assertIn('date', first_item)
            self.assertIn('judgment', first_item)
            self.assertIn('total_quantity', first_item)
            self.assertIn('total_count', first_item)
    
    def test_get_part_analysis(self):
        """機種別分析のテスト"""
        start_date = self.week_start
        end_date = self.week_start + timedelta(days=6)
        
        result = self.service.get_part_analysis(self.line.name, "製品X", start_date, end_date)
        
        # 結果がリストであることを確認
        self.assertIsInstance(result, list)
        
        # データが存在する場合の構造をチェック
        if result:
            first_item = result[0]
            self.assertIn('date', first_item)
            self.assertIn('judgment', first_item)
            self.assertIn('total_quantity', first_item)
            self.assertIn('total_count', first_item)
    
    def test_get_performance_metrics(self):
        """パフォーマンス指標のテスト"""
        result = self.service.get_performance_metrics(self.line.id, self.week_dates)
        
        # 基本指標の確認
        expected_keys = [
            'total_production', 'total_defects', 'defect_rate', 'working_days',
            'daily_average', 'part_count', 'machine_count', 'production_stability',
            'total_operations', 'efficiency_score'
        ]
        
        for key in expected_keys:
            self.assertIn(key, result)
        
        # 数値の妥当性確認
        self.assertGreaterEqual(result['total_production'], 0)
        self.assertGreaterEqual(result['defect_rate'], 0)
        self.assertLessEqual(result['defect_rate'], 100)
        self.assertGreaterEqual(result['working_days'], 0)
        self.assertLessEqual(result['working_days'], 7)
    
    def test_get_hourly_trend_structure(self):
        """時間別トレンドの構造テスト"""
        # モックを使用してget_dashboard_dataをスキップ
        with self.patch_dashboard_data():
            result = self.service.get_hourly_trend(self.line.id, self.test_date)
        
        # 基本構造の確認
        expected_keys = ['date', 'line_name', 'hourly_trend', 'peak_hour', 'lowest_hour', 'average_efficiency']
        for key in expected_keys:
            self.assertIn(key, result)
        
        # 日付の確認
        self.assertEqual(result['date'], self.test_date.strftime('%Y-%m-%d'))
        self.assertEqual(result['line_name'], self.line.name)
    
    def test_invalid_line_handling(self):
        """無効なライン ID の処理テスト"""
        # 週別データ取得
        result = self.service.get_weekly_data(999, self.test_date)
        self.assertEqual(result, {})
        
        # 機種別分析
        result = self.service.get_part_analysis(999, self.week_dates)
        self.assertEqual(result, [])
        
        # パフォーマンス指標
        result = self.service.get_performance_metrics(999, self.week_dates)
        self.assertEqual(result, {})
        
        # 時間別トレンド
        result = self.service.get_hourly_trend(999, self.test_date)
        self.assertEqual(result, {})
    
    def test_empty_data_handling(self):
        """空データの処理テスト"""
        # 集計データを削除
        WeeklyResultAggregation.objects.all().delete()
        
        # 機種別分析（空データ）
        result = self.service.get_part_analysis(self.line.id, self.week_dates)
        self.assertEqual(result, [])
        
        # パフォーマンス指標（空データ）
        result = self.service.get_performance_metrics(self.line.id, self.week_dates)
        
        # 空データでも基本構造は返される
        self.assertIn('total_production', result)
        self.assertEqual(result['total_production'], 0)
        self.assertEqual(result['working_days'], 0)
    
    def patch_dashboard_data(self):
        """get_dashboard_data をモックするコンテキストマネージャー"""
        from unittest.mock import patch
        
        def mock_get_dashboard_data(line_id, date_str):
            return {
                'total_planned': 100,
                'total_actual': 80,
                'hourly': [
                    {'hour': '08:00', 'total_planned': 10, 'total_actual': 8},
                    {'hour': '09:00', 'total_planned': 10, 'total_actual': 9},
                    {'hour': '10:00', 'total_planned': 10, 'total_actual': 7},
                ]
            }
        
        return patch('production.utils.get_dashboard_data', side_effect=mock_get_dashboard_data)