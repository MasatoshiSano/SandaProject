"""
AggregationService のテスト
"""

from datetime import date, datetime, time
from django.test import TestCase, override_settings
from django.utils import timezone
from production.models import Line, WeeklyResultAggregation
from production.services import AggregationService


# テスト用のシンプルなデータベース設定
@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    DATABASE_ROUTERS=[]  # ルーターを無効化
)
class TestAggregationService(TestCase):
    """AggregationService のテストクラス"""
    
    def setUp(self):
        """テスト用データの準備"""
        self.service = AggregationService()
        
        # テスト用ライン作成
        self.line = Line.objects.create(
            name="テストライン1",
            description="テスト用ライン"
        )
        
        self.test_date = date(2025, 1, 15)
    
    def test_aggregation_service_creation(self):
        """AggregationService の作成テスト"""
        service = AggregationService()
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.logger)
    
    def test_empty_data_aggregation(self):
        """空データの集計テスト"""
        # 実績データがない状態で集計実行
        count = self.service.aggregate_single_date(self.line.id, self.test_date)
        
        # 結果確認
        self.assertEqual(count, 0)
        
        # 集計レコードが作成されていないことを確認
        aggregation_count = WeeklyResultAggregation.objects.filter(
            line=self.line.name,
            date=self.test_date
        ).count()
        self.assertEqual(aggregation_count, 0)
    
    def test_invalid_line_handling(self):
        """無効なライン ID の処理テスト"""
        with self.assertRaises(Line.DoesNotExist):
            self.service.aggregate_single_date(999, self.test_date)
        
        # 検証でも同様
        is_valid = self.service.validate_aggregation(999, self.test_date)
        self.assertFalse(is_valid)
    
    def test_date_range_aggregation(self):
        """期間集計のテスト"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 17)
        
        # 期間集計実行（データがない状態）
        total_count = self.service.aggregate_date_range(
            self.line.id, 
            start_date, 
            end_date
        )
        
        # 結果確認（データがないので0）
        self.assertEqual(total_count, 0)
    
    def test_aggregation_summary(self):
        """集計サマリーのテスト"""
        # サマリー取得
        summary = self.service.get_aggregation_summary(self.line.id, self.test_date)
        
        # 結果確認
        self.assertEqual(summary['line_name'], self.line.name)
        self.assertEqual(summary['date'], self.test_date)
        self.assertEqual(summary['total_records'], 0)  # データがないので0
        self.assertEqual(summary['total_quantity'], 0)
        self.assertTrue(summary['is_consistent'])  # 空データは整合性OK
    
    def test_repair_aggregation(self):
        """集計修復のテスト"""
        # 修復実行（データがない状態）
        result = self.service.repair_aggregation(self.line.id, self.test_date)
        
        # 結果確認
        self.assertTrue(result)  # 空データは修復不要でTrue
    
    def test_detect_inconsistencies(self):
        """不整合検出のテスト"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 17)
        
        # 不整合検出実行
        inconsistent_dates = self.service.detect_inconsistencies(
            self.line.id, 
            start_date, 
            end_date
        )
        
        # 結果確認（データがないので不整合なし）
        self.assertEqual(len(inconsistent_dates), 0)
    
    def test_batch_repair(self):
        """一括修復のテスト"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 17)
        
        # 一括修復実行
        result = self.service.batch_repair(self.line.id, start_date, end_date)
        
        # 結果確認
        self.assertEqual(result['total_days'], 3)
        self.assertEqual(result['inconsistent_days'], 0)
        self.assertEqual(result['repaired_days'], 0)
        self.assertEqual(result['failed_days'], 0)
        self.assertEqual(result['success_rate'], 100.0)