"""
シグナル処理のテスト
"""

from datetime import date, datetime, time
from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch, MagicMock
from production.models import Line, Result, WeeklyResultAggregation


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    DATABASE_ROUTERS=[]  # ルーターを無効化
)
class TestResultSignals(TestCase):
    """Result モデルのシグナルテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        # テスト用ライン作成
        self.line = Line.objects.create(
            name="テストライン1",
            description="テスト用ライン"
        )
        
        self.test_date = date(2025, 1, 15)
        self.test_datetime = timezone.make_aware(
            datetime.combine(self.test_date, time(10, 0))
        )
    
    def test_result_save_signal(self):
        """実績保存時のシグナルテスト"""
        # シグナルハンドラーが登録されていることを確認
        from django.db.models.signals import post_save
        from production.models import Result, update_aggregation_on_result_save
        
        # シグナルハンドラーが登録されているかチェック
        handlers = post_save._live_receivers(sender=Result)
        handler_functions = [handler.__name__ for handler in handlers if hasattr(handler, '__name__')]
        
        self.assertIn('update_aggregation_on_result_save', handler_functions)
        
        # 実績データを作成（シグナルが発火される）
        result = Result.objects.create(
            line=self.line.name,
            machine="機械A",
            part="製品X",
            timestamp=self.test_datetime,
            serial_number="SN001",
            judgment="OK",
            quantity=5
        )
        
        # 実績データが正常に作成されることを確認
        self.assertIsNotNone(result.id)
    
    def test_result_delete_signal(self):
        """実績削除時のシグナルテスト"""
        # シグナルハンドラーが登録されていることを確認
        from django.db.models.signals import post_delete
        from production.models import Result, update_aggregation_on_result_delete
        
        # シグナルハンドラーが登録されているかチェック
        handlers = post_delete._live_receivers(sender=Result)
        handler_functions = [handler.__name__ for handler in handlers if hasattr(handler, '__name__')]
        
        self.assertIn('update_aggregation_on_result_delete', handler_functions)
        
        # 実績データを作成
        result = Result.objects.create(
            line=self.line.name,
            machine="機械A",
            part="製品X",
            timestamp=self.test_datetime,
            serial_number="SN001",
            judgment="OK",
            quantity=5
        )
        
        result_id = result.id
        
        # 実績データを削除（シグナルが発火される）
        result.delete()
        
        # データが削除されたことを確認
        self.assertFalse(Result.objects.filter(id=result_id).exists())
    
    def test_result_update_signal(self):
        """実績更新時のシグナルテスト"""
        # 実績データを作成
        result = Result.objects.create(
            line=self.line.name,
            machine="機械A",
            part="製品X",
            timestamp=self.test_datetime,
            serial_number="SN001",
            judgment="OK",
            quantity=5
        )
        
        # 実績データを更新
        result.quantity = 10
        result.save()
        
        # データが更新されたことを確認
        updated_result = Result.objects.get(id=result.id)
        self.assertEqual(updated_result.quantity, 10)
    
    def test_signal_registration(self):
        """シグナル登録のテスト"""
        from django.db.models.signals import post_save, post_delete
        from production.models import Result
        
        # post_save シグナルの確認
        save_handlers = post_save._live_receivers(sender=Result)
        self.assertGreater(len(save_handlers), 0)
        
        # post_delete シグナルの確認
        delete_handlers = post_delete._live_receivers(sender=Result)
        self.assertGreater(len(delete_handlers), 0)
    
    def test_signal_with_empty_data(self):
        """空データでのシグナルテスト"""
        # ライン名や機種名が空の実績データを作成
        result = Result.objects.create(
            line="",  # 空のライン名
            machine="機械A",
            part="",  # 空の機種名
            timestamp=self.test_datetime,
            serial_number="SN001",
            judgment="OK",
            quantity=5
        )
        
        # 実績データが作成されることを確認
        self.assertIsNotNone(result.id)
        
        # シグナルは発火するが、AggregationService内で適切に処理される
        # （空データはスキップされる）
    
    def test_retry_function(self):
        """リトライ機能のテスト"""
        from production.models import retry_with_backoff
        
        # 成功するケース
        def success_func():
            return "success"
        
        result = retry_with_backoff(success_func, max_retries=2, base_delay=0.01)
        self.assertEqual(result, "success")
        
        # 失敗するケース
        def fail_func():
            raise Exception("テストエラー")
        
        with self.assertRaises(Exception):
            retry_with_backoff(fail_func, max_retries=1, base_delay=0.01)
    
    def test_fallback_scheduling(self):
        """フォールバック機能のテスト"""
        from production.utils import schedule_full_reaggregation
        
        # 正常なケース
        result = schedule_full_reaggregation(self.line.id, self.test_date)
        self.assertTrue(result)
        
        # 無効なライン ID のケース
        result = schedule_full_reaggregation(999, self.test_date)
        self.assertFalse(result)