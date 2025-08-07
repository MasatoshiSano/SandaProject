"""
Input count functionality unit tests
"""
from django.test import TestCase
from django.contrib.auth.models import User
from datetime import datetime, date, time, timedelta
from unittest.mock import patch, MagicMock
import logging

from production.models import Line, Machine, WorkCalendar, Result
from production.utils import calculate_input_count, get_dashboard_data


class InputCountCalculationTest(TestCase):
    """投入数計算機能のテスト"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        # ログレベルを設定（テスト中のログ出力を抑制）
        logging.disable(logging.WARNING)
        
        # テストライン作成
        self.line = Line.objects.create(
            name='テストライン',
            description='テスト用ライン',
            is_active=True
        )
        
        # テスト設備作成（投入数対象）
        self.machine_target = Machine.objects.create(
            name='設備A',
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        
        # テスト設備作成（投入数対象外）
        self.machine_non_target = Machine.objects.create(
            name='設備B',
            line=self.line,
            is_active=True,
            is_count_target=False
        )
        
        # 稼働カレンダー作成
        self.work_calendar = WorkCalendar.objects.create(
            line=self.line,
            work_start_time=time(8, 30),
            morning_meeting_duration=15
        )
        
        # テスト日付
        self.test_date = date(2025, 1, 15)
        self.test_date_str = '2025-01-15'
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        logging.disable(logging.NOTSET)
    
    @patch('production.utils.Result.objects.filter')
    def test_calculate_input_count_with_target_machines(self, mock_filter):
        """投入数対象設備がある場合の投入数計算テスト"""
        # モックの設定
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 150
        mock_filter.return_value = mock_queryset
        
        # 投入数計算実行
        result = calculate_input_count(self.line.id, self.test_date_str)
        
        # 結果検証
        self.assertEqual(result, 150)
        
        # フィルタ条件の検証
        mock_filter.assert_called_once()
        call_args = mock_filter.call_args[1]
        self.assertEqual(call_args['line'], self.line.name)
        self.assertIn(self.machine_target.name, call_args['machine__in'])
        self.assertNotIn(self.machine_non_target.name, call_args['machine__in'])
        self.assertEqual(call_args['sta_no1'], 'SAND')
    
    def test_calculate_input_count_no_target_machines(self):
        """投入数対象設備がない場合のテスト"""
        # 投入数対象設備を無効化
        self.machine_target.is_count_target = False
        self.machine_target.save()
        
        # 投入数計算実行
        result = calculate_input_count(self.line.id, self.test_date_str)
        
        # 結果検証（0が返される）
        self.assertEqual(result, 0)
    
    def test_calculate_input_count_no_work_calendar(self):
        """稼働カレンダーがない場合のテスト"""
        # 稼働カレンダーを削除
        self.work_calendar.delete()
        
        with patch('production.utils.Result.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 100
            mock_filter.return_value = mock_queryset
            
            # 投入数計算実行
            result = calculate_input_count(self.line.id, self.test_date_str)
            
            # 結果検証（デフォルト時間で計算される）
            self.assertEqual(result, 100)
            
            # デフォルト時間（8:30）が使用されることを確認
            call_args = mock_filter.call_args[1]
            self.assertIn('20250115083000', call_args['timestamp__gte'])
    
    def test_calculate_input_count_invalid_date(self):
        """無効な日付形式の場合のテスト"""
        result = calculate_input_count(self.line.id, 'invalid-date')
        self.assertEqual(result, 0)
    
    def test_calculate_input_count_invalid_line_id(self):
        """無効なライン IDの場合のテスト"""
        result = calculate_input_count(99999, self.test_date_str)
        self.assertEqual(result, 0)
    
    def test_calculate_input_count_time_period_calculation(self):
        """時間期間計算のテスト"""
        with patch('production.utils.Result.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 50
            mock_filter.return_value = mock_queryset
            
            # 投入数計算実行
            calculate_input_count(self.line.id, self.test_date_str)
            
            # 時間期間の検証
            call_args = mock_filter.call_args[1]
            
            # 開始時刻: 2025-01-15 08:30:00
            expected_start = '20250115083000'
            self.assertEqual(call_args['timestamp__gte'], expected_start)
            
            # 終了時刻: 2025-01-16 08:30:00
            expected_end = '20250116083000'
            self.assertEqual(call_args['timestamp__lt'], expected_end)
    
    @patch('production.utils.Result.objects.filter')
    def test_calculate_input_count_includes_all_judgments(self, mock_filter):
        """全判定（OK/NG）が含まれることのテスト"""
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 200
        mock_filter.return_value = mock_queryset
        
        # 投入数計算実行
        result = calculate_input_count(self.line.id, self.test_date_str)
        
        # フィルタ条件に judgment が含まれていないことを確認
        call_args = mock_filter.call_args[1]
        self.assertNotIn('judgment', call_args)
        
        # 結果検証
        self.assertEqual(result, 200)
    
    @patch('production.utils.Result.objects.filter')
    def test_calculate_input_count_database_error(self, mock_filter):
        """データベースエラーの場合のテスト"""
        # データベースエラーをシミュレート
        mock_filter.side_effect = Exception("Database connection error")
        
        # 投入数計算実行
        result = calculate_input_count(self.line.id, self.test_date_str)
        
        # エラー時は0が返される
        self.assertEqual(result, 0)


class DashboardDataInputCountTest(TestCase):
    """ダッシュボードデータの投入数統合テスト"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        logging.disable(logging.WARNING)
        
        # テストライン作成
        self.line = Line.objects.create(
            name='ダッシュボードテストライン',
            description='ダッシュボード用テストライン',
            is_active=True
        )
        
        # テスト設備作成
        self.machine = Machine.objects.create(
            name='ダッシュボード設備',
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        
        # 稼働カレンダー作成
        self.work_calendar = WorkCalendar.objects.create(
            line=self.line,
            work_start_time=time(9, 0),
            morning_meeting_duration=10
        )
        
        self.test_date_str = '2025-01-15'
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        logging.disable(logging.NOTSET)
    
    @patch('production.utils.calculate_input_count')
    @patch('production.utils.get_count_target_machines')
    @patch('production.utils.Result.objects.filter')
    def test_get_dashboard_data_includes_input_count(self, mock_result_filter, mock_get_machines, mock_calc_input):
        """ダッシュボードデータに投入数が含まれることのテスト"""
        # モックの設定
        mock_get_machines.return_value = [self.machine]
        mock_result_filter.return_value = MagicMock()
        mock_calc_input.return_value = 300
        
        # ダッシュボードデータ取得
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        
        # 投入数が含まれることを確認
        self.assertIn('input_count', dashboard_data)
        self.assertEqual(dashboard_data['input_count'], 300)
        
        # calculate_input_count が正しい引数で呼ばれることを確認
        mock_calc_input.assert_called_once_with(self.line.id, self.test_date_str)
    
    @patch('production.utils.calculate_input_count')
    @patch('production.utils.get_count_target_machines')
    @patch('production.utils.Result.objects.filter')
    def test_get_dashboard_data_input_count_error_handling(self, mock_result_filter, mock_get_machines, mock_calc_input):
        """投入数計算エラー時のダッシュボードデータテスト"""
        # モックの設定
        mock_get_machines.return_value = [self.machine]
        mock_result_filter.return_value = MagicMock()
        mock_calc_input.side_effect = Exception("Input count calculation error")
        
        # ダッシュボードデータ取得
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        
        # エラー時でも投入数が0で含まれることを確認
        self.assertIn('input_count', dashboard_data)
        self.assertEqual(dashboard_data['input_count'], 0)
        
        # 他のデータは正常に取得されることを確認
        self.assertIn('total_planned', dashboard_data)
        self.assertIn('total_actual', dashboard_data)
        self.assertIn('achievement_rate', dashboard_data)
        self.assertIn('remaining', dashboard_data)
    
    @patch('production.utils.calculate_input_count')
    @patch('production.utils.get_count_target_machines')
    @patch('production.utils.Result.objects.filter')
    def test_dashboard_data_backward_compatibility(self, mock_result_filter, mock_get_machines, mock_calc_input):
        """ダッシュボードデータの後方互換性テスト"""
        # モックの設定
        mock_get_machines.return_value = [self.machine]
        mock_result_filter.return_value = MagicMock()
        mock_calc_input.return_value = 150
        
        # ダッシュボードデータ取得
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        
        # 既存のフィールドが全て含まれることを確認
        expected_fields = [
            'parts', 'hourly', 'total_planned', 'total_actual',
            'achievement_rate', 'remaining', 'last_updated', 'input_count'
        ]
        
        for field in expected_fields:
            self.assertIn(field, dashboard_data, f"Field '{field}' is missing from dashboard data")


class InputCountMachineConfigurationTest(TestCase):
    """投入数設備設定のテスト"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        logging.disable(logging.WARNING)
        
        # テストライン作成
        self.line = Line.objects.create(
            name='設定テストライン',
            is_active=True
        )
        
        # 複数の設備を作成
        self.machines = []
        for i in range(5):
            machine = Machine.objects.create(
                name=f'設備{i+1}',
                line=self.line,
                is_active=True,
                is_count_target=(i % 2 == 0)  # 偶数番号の設備のみ投入数対象
            )
            self.machines.append(machine)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        logging.disable(logging.NOTSET)
    
    @patch('production.utils.Result.objects.filter')
    def test_only_target_machines_included(self, mock_filter):
        """投入数対象設備のみが計算に含まれることのテスト"""
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 100
        mock_filter.return_value = mock_queryset
        
        # 投入数計算実行
        calculate_input_count(self.line.id, '2025-01-15')
        
        # フィルタ条件の確認
        call_args = mock_filter.call_args[1]
        machine_names = call_args['machine__in']
        
        # 投入数対象設備のみが含まれることを確認
        expected_machines = ['設備1', '設備3', '設備5']  # 偶数番号（0, 2, 4）
        self.assertEqual(sorted(machine_names), sorted(expected_machines))
    
    def test_inactive_machines_excluded(self):
        """非アクティブ設備が除外されることのテスト"""
        # 投入数対象設備の一つを非アクティブにする
        self.machines[0].is_active = False
        self.machines[0].save()
        
        with patch('production.utils.Result.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 50
            mock_filter.return_value = mock_queryset
            
            # 投入数計算実行
            calculate_input_count(self.line.id, '2025-01-15')
            
            # フィルタ条件の確認
            call_args = mock_filter.call_args[1]
            machine_names = call_args['machine__in']
            
            # 非アクティブ設備が除外されることを確認
            self.assertNotIn('設備1', machine_names)
            self.assertIn('設備3', machine_names)
            self.assertIn('設備5', machine_names)
    
    def test_machine_configuration_changes(self):
        """設備設定変更時の動作テスト"""
        # 初期状態での投入数対象設備数を確認
        target_machines = Machine.objects.filter(
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        initial_count = target_machines.count()
        self.assertEqual(initial_count, 3)  # 設備1, 3, 5
        
        # 設備の投入数対象フラグを変更
        self.machines[1].is_count_target = True  # 設備2を対象に追加
        self.machines[1].save()
        
        self.machines[2].is_count_target = False  # 設備3を対象から除外
        self.machines[2].save()
        
        # 変更後の投入数対象設備数を確認
        target_machines = Machine.objects.filter(
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        final_count = target_machines.count()
        self.assertEqual(final_count, 3)  # 設備1, 2, 5
        
        # 対象設備名を確認
        target_names = list(target_machines.values_list('name', flat=True))
        expected_names = ['設備1', '設備2', '設備5']
        self.assertEqual(sorted(target_names), sorted(expected_names))