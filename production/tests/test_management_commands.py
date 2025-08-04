"""
管理コマンドのテスト
"""

from datetime import date, timedelta
from io import StringIO
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from production.models import Line, WeeklyResultAggregation, Result
from django.utils import timezone


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    DATABASE_ROUTERS=[]  # ルーターを無効化
)
class TestAggregateResultsCommand(TestCase):
    """aggregate_results管理コマンドのテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        # テスト用ライン作成
        self.line1 = Line.objects.create(
            name="テストライン1",
            description="テスト用ライン1"
        )
        
        self.line2 = Line.objects.create(
            name="テストライン2",
            description="テスト用ライン2"
        )
        
        # テスト用日付
        self.test_date = date(2025, 1, 15)
        
        # テスト用実績データを作成
        self._create_test_result_data()
    
    def _create_test_result_data(self):
        """テスト用の実績データを作成"""
        test_datetime = timezone.make_aware(
            timezone.datetime.combine(self.test_date, timezone.datetime.min.time())
        )
        
        # ライン1のデータ
        Result.objects.create(
            line=self.line1.name,
            machine="機械A",
            part="製品X",
            timestamp=test_datetime,
            serial_number="SN001",
            judgment="OK",
            quantity=10
        )
        
        Result.objects.create(
            line=self.line1.name,
            machine="機械A",
            part="製品X",
            timestamp=test_datetime + timedelta(hours=1),
            serial_number="SN002",
            judgment="NG",
            quantity=2
        )
        
        # ライン2のデータ
        Result.objects.create(
            line=self.line2.name,
            machine="機械B",
            part="製品Y",
            timestamp=test_datetime,
            serial_number="SN003",
            judgment="OK",
            quantity=5
        )
    
    def test_single_line_single_date(self):
        """単一ライン・単一日付の集計テスト"""
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        # 出力の確認
        output = out.getvalue()
        self.assertIn('集計処理が正常に完了しました', output)
        self.assertIn(self.line1.name, output)
        
        # 集計データの確認
        aggregations = WeeklyResultAggregation.objects.filter(
            line=self.line1.name,
            date=self.test_date
        )
        
        self.assertGreater(aggregations.count(), 0)
        
        # OK判定のデータ確認
        ok_agg = aggregations.filter(judgment='OK').first()
        self.assertIsNotNone(ok_agg)
        self.assertEqual(ok_agg.total_quantity, 10)
        
        # NG判定のデータ確認
        ng_agg = aggregations.filter(judgment='NG').first()
        self.assertIsNotNone(ng_agg)
        self.assertEqual(ng_agg.total_quantity, 2)
    
    def test_all_lines_single_date(self):
        """全ライン・単一日付の集計テスト"""
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--all-lines',
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        # 出力の確認
        output = out.getvalue()
        self.assertIn('集計処理が正常に完了しました', output)
        self.assertIn(self.line1.name, output)
        self.assertIn(self.line2.name, output)
        
        # 両ラインの集計データが作成されていることを確認
        line1_aggregations = WeeklyResultAggregation.objects.filter(
            line=self.line1.name,
            date=self.test_date
        )
        self.assertGreater(line1_aggregations.count(), 0)
        
        line2_aggregations = WeeklyResultAggregation.objects.filter(
            line=self.line2.name,
            date=self.test_date
        )
        self.assertGreater(line2_aggregations.count(), 0)
    
    def test_date_range_aggregation(self):
        """日付範囲の集計テスト"""
        start_date = self.test_date
        end_date = self.test_date + timedelta(days=2)
        
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--start-date', start_date.strftime('%Y-%m-%d'),
            '--end-date', end_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        # 出力の確認
        output = out.getvalue()
        self.assertIn('集計処理が正常に完了しました', output)
        self.assertIn('対象日付数: 3', output)
        
        # 3日分の処理が行われたことを確認（実際のデータは1日分のみ）
        self.assertIn('[100.0%]', output)
    
    def test_force_option(self):
        """強制再作成オプションのテスト"""
        # 最初の集計
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=StringIO()
        )
        
        initial_count = WeeklyResultAggregation.objects.filter(
            line=self.line1.name,
            date=self.test_date
        ).count()
        
        # 強制再作成なしで再実行
        out = StringIO()
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('スキップ（既存データあり', output)
        
        # 強制再作成ありで再実行
        out = StringIO()
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--force',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('強制再作成モード', output)
        self.assertIn('完了', output)
        
        # データ数が変わっていないことを確認（再作成されたため）
        final_count = WeeklyResultAggregation.objects.filter(
            line=self.line1.name,
            date=self.test_date
        ).count()
        self.assertEqual(initial_count, final_count)
    
    def test_validate_option(self):
        """データ整合性検証オプションのテスト"""
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--validate',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('データ整合性検証: 有効', output)
        self.assertIn('集計処理が正常に完了しました', output)
    
    def test_dry_run_option(self):
        """ドライランオプションのテスト"""
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--dry-run',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('ドライランモード', output)
        self.assertIn('実際の処理は行いません', output)
        
        # 実際にはデータが作成されていないことを確認
        aggregations = WeeklyResultAggregation.objects.filter(
            line=self.line1.name,
            date=self.test_date
        )
        self.assertEqual(aggregations.count(), 0)
    
    def test_invalid_arguments(self):
        """無効な引数のテスト"""
        # ライン指定なし
        with self.assertRaises(CommandError):
            call_command(
                'aggregate_results',
                '--date', self.test_date.strftime('%Y-%m-%d'),
                stdout=StringIO()
            )
        
        # 日付指定なし
        with self.assertRaises(CommandError):
            call_command(
                'aggregate_results',
                '--line-id', str(self.line1.id),
                stdout=StringIO()
            )
        
        # 無効な日付形式
        with self.assertRaises(CommandError):
            call_command(
                'aggregate_results',
                '--line-id', str(self.line1.id),
                '--date', 'invalid-date',
                stdout=StringIO()
            )
        
        # 存在しないライン ID
        with self.assertRaises(CommandError):
            call_command(
                'aggregate_results',
                '--line-id', '999',
                '--date', self.test_date.strftime('%Y-%m-%d'),
                stdout=StringIO()
            )
    
    def test_progress_display(self):
        """進捗表示のテスト"""
        start_date = self.test_date
        end_date = self.test_date + timedelta(days=1)
        
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--start-date', start_date.strftime('%Y-%m-%d'),
            '--end-date', end_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        output = out.getvalue()
        
        # 進捗表示の確認
        self.assertIn('[50.0%]', output)  # 1日目完了時
        self.assertIn('[100.0%]', output)  # 2日目完了時
        
        # サマリー情報の確認
        self.assertIn('=== 集計処理サマリー ===', output)
        self.assertIn('=== 処理結果 ===', output)
        self.assertIn('総処理数: 2', output)
    
    def test_batch_processing(self):
        """バッチ処理のテスト"""
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--batch-size', '50',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('集計処理が正常に完了しました', output)
        
        # 集計データが正常に作成されていることを確認
        aggregations = WeeklyResultAggregation.objects.filter(
            line=self.line1.name,
            date=self.test_date
        )
        self.assertGreater(aggregations.count(), 0)
    
    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        # 無効なライン ID でのテスト（存在しないライン）
        with self.assertRaises(CommandError):
            call_command(
                'aggregate_results',
                '--line-id', '999',
                '--date', self.test_date.strftime('%Y-%m-%d'),
                stdout=StringIO()
            )
    
    def test_summary_display(self):
        """サマリー表示のテスト"""
        out = StringIO()
        
        call_command(
            'aggregate_results',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        output = out.getvalue()
        
        # サマリー情報の確認
        self.assertIn('=== 集計処理サマリー ===', output)
        self.assertIn(f'対象ライン数: 1', output)
        self.assertIn(f'対象日付数: 1', output)
        self.assertIn(f'{self.line1.name}', output)
        self.assertIn(f'{self.test_date}', output)
        self.assertIn('推定処理時間', output)


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    DATABASE_ROUTERS=[]  # ルーターを無効化
)
class TestValidateAggregationCommand(TestCase):
    """validate_aggregation管理コマンドのテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        # テスト用ライン作成
        self.line1 = Line.objects.create(
            name="検証テストライン1",
            description="検証テスト用ライン1"
        )
        
        # テスト用日付
        self.test_date = date(2025, 1, 15)
        
        # テスト用実績データを作成
        self._create_test_result_data()
        
        # 集計データを作成
        self._create_test_aggregation_data()
    
    def _create_test_result_data(self):
        """テスト用の実績データを作成"""
        test_datetime = timezone.make_aware(
            timezone.datetime.combine(self.test_date, timezone.datetime.min.time())
        )
        
        Result.objects.create(
            line=self.line1.name,
            machine="機械A",
            part="製品X",
            timestamp=test_datetime,
            serial_number="SN001",
            judgment="OK",
            quantity=10
        )
        
        Result.objects.create(
            line=self.line1.name,
            machine="機械A",
            part="製品X",
            timestamp=test_datetime + timedelta(hours=1),
            serial_number="SN002",
            judgment="NG",
            quantity=2
        )
    
    def _create_test_aggregation_data(self):
        """テスト用の集計データを作成"""
        # 正しい集計データ
        WeeklyResultAggregation.objects.create(
            date=self.test_date,
            line=self.line1.name,
            machine="機械A",
            part="製品X",
            judgment="OK",
            total_quantity=10,
            result_count=1
        )
        
        WeeklyResultAggregation.objects.create(
            date=self.test_date,
            line=self.line1.name,
            machine="機械A",
            part="製品X",
            judgment="NG",
            total_quantity=2,
            result_count=1
        )
    
    def test_validate_consistent_data(self):
        """整合性のあるデータの検証テスト"""
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        output = out.getvalue()
        
        # 成功メッセージの確認
        self.assertIn('すべてのデータが整合性を保っています', output)
        self.assertIn('=== 検証結果 ===', output)
        self.assertIn('整合性OK: 1', output)
        self.assertIn('不整合検出: 0', output)
    
    def test_validate_inconsistent_data(self):
        """不整合データの検証テスト"""
        # 集計データを意図的に破損
        agg = WeeklyResultAggregation.objects.filter(judgment='OK').first()
        agg.total_quantity = 999  # 不正な値に変更
        agg.save()
        
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        output = out.getvalue()
        
        # 不整合検出メッセージの確認
        self.assertIn('不整合が検出されました', output)
        self.assertIn('不整合検出: 1', output)
        self.assertIn('--repair オプションで修復できます', output)
    
    def test_validate_with_repair(self):
        """修復オプション付き検証テスト"""
        # 集計データを意図的に破損
        agg = WeeklyResultAggregation.objects.filter(judgment='OK').first()
        agg.total_quantity = 999
        agg.save()
        
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--repair',
            stdout=out
        )
        
        output = out.getvalue()
        
        # 修復メッセージの確認
        self.assertIn('不整合を修復しました', output)
        self.assertIn('修復成功: 1', output)
    
    def test_validate_detailed_mode(self):
        """詳細モードの検証テスト"""
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--detailed',
            stdout=out
        )
        
        output = out.getvalue()
        
        # 詳細モードの確認
        self.assertIn('詳細モード', output)
        self.assertIn('整合性OK', output)
    
    def test_validate_all_lines(self):
        """全ライン検証テスト"""
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--all-lines',
            '--date', self.test_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        output = out.getvalue()
        
        # 全ライン処理の確認
        self.assertIn('対象ライン数:', output)
        self.assertIn(self.line1.name, output)
    
    def test_validate_date_range(self):
        """日付範囲検証テスト"""
        start_date = self.test_date
        end_date = self.test_date + timedelta(days=1)
        
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--line-id', str(self.line1.id),
            '--start-date', start_date.strftime('%Y-%m-%d'),
            '--end-date', end_date.strftime('%Y-%m-%d'),
            stdout=out
        )
        
        output = out.getvalue()
        
        # 日付範囲処理の確認
        self.assertIn('対象日付数: 2', output)
    
    def test_validate_no_aggregation_data(self):
        """集計データがない場合の検証テスト"""
        # 集計データを削除
        WeeklyResultAggregation.objects.all().delete()
        
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--detailed',
            stdout=out
        )
        
        output = out.getvalue()
        
        # 集計データなしの確認
        self.assertIn('集計データなし', output)
    
    def test_validate_invalid_arguments(self):
        """無効な引数のテスト"""
        # ライン指定なし
        with self.assertRaises(CommandError):
            call_command(
                'validate_aggregation',
                '--date', self.test_date.strftime('%Y-%m-%d'),
                stdout=StringIO()
            )
        
        # 修復とレポートオンリーの競合
        with self.assertRaises(CommandError):
            call_command(
                'validate_aggregation',
                '--line-id', str(self.line1.id),
                '--date', self.test_date.strftime('%Y-%m-%d'),
                '--repair',
                '--report-only',
                stdout=StringIO()
            )
    
    def test_validate_report_only_mode(self):
        """レポートオンリーモードのテスト"""
        # 集計データを意図的に破損
        agg = WeeklyResultAggregation.objects.filter(judgment='OK').first()
        original_quantity = agg.total_quantity
        agg.total_quantity = 999
        agg.save()
        
        out = StringIO()
        
        call_command(
            'validate_aggregation',
            '--line-id', str(self.line1.id),
            '--date', self.test_date.strftime('%Y-%m-%d'),
            '--report-only',
            stdout=out
        )
        
        output = out.getvalue()
        
        # レポートモードの確認
        self.assertIn('レポートモード', output)
        self.assertIn('不整合検出: 1', output)
        
        # データが修復されていないことを確認
        agg.refresh_from_db()
        self.assertEqual(agg.total_quantity, 999)  # 変更されていない