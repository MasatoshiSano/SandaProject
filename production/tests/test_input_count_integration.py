"""
Input count integration tests
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, date, time, timedelta
import json
import logging
from unittest.mock import patch, MagicMock

from production.models import Line, Machine, WorkCalendar, Part, Plan
from production.utils import get_dashboard_data


class DashboardInputCountIntegrationTest(TestCase):
    """ダッシュボード投入数統合テスト"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        # ログレベルを設定
        logging.disable(logging.WARNING)
        
        # テストユーザー作成
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            is_superuser=True
        )
        
        # テストライン作成
        self.line = Line.objects.create(
            name='統合テストライン',
            description='統合テスト用ライン',
            is_active=True
        )
        
        # テスト設備作成
        self.machine_target1 = Machine.objects.create(
            name='投入数設備1',
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        
        self.machine_target2 = Machine.objects.create(
            name='投入数設備2',
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        
        self.machine_non_target = Machine.objects.create(
            name='非投入数設備',
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
        
        # テスト機種作成
        from production.models import Category
        category = Category.objects.create(name='テストカテゴリ')
        self.part = Part.objects.create(
            name='テスト機種',
            line=self.line,
            category=category,
            target_pph=100
        )
        
        # テスト日付
        self.test_date = date(2025, 1, 15)
        self.test_date_str = '2025-01-15'
        
        # クライアント設定
        self.client = Client()
        self.client.force_login(self.user)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        logging.disable(logging.NOTSET)
    
    def mock_result_filter(self, count_target1=10, count_target2=15, count_non_target=5):
        """テスト用実績データをモック"""
        def filter_side_effect(**kwargs):
            mock_queryset = MagicMock()
            
            # 投入数対象設備のみをカウント
            machine_names = kwargs.get('machine__in', [])
            total_count = 0
            
            if self.machine_target1.name in machine_names:
                total_count += count_target1
            if self.machine_target2.name in machine_names:
                total_count += count_target2
            # 非投入数対象設備は除外
            
            mock_queryset.count.return_value = total_count
            return mock_queryset
        
        return filter_side_effect
    
    @patch('production.utils.Result.objects.filter')
    def test_dashboard_api_includes_input_count(self, mock_result_filter):
        """ダッシュボードAPIが投入数を含むことのテスト"""
        # モック設定
        mock_result_filter.side_effect = self.mock_result_filter(count_target1=20, count_target2=30, count_non_target=10)
        
        # API呼び出し（正しいURL名を使用）
        url = f'/production/api/dashboard-data/{self.line.id}/{self.test_date_str}/'
        response = self.client.get(url)
        
        # レスポンス検証
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        
        # 投入数が含まれることを確認
        self.assertIn('input_count', data)
        
        # 投入数が正しく計算されることを確認（投入数対象設備のみ）
        expected_input_count = 20 + 30  # 非投入数対象設備は除外
        self.assertEqual(data['input_count'], expected_input_count)
        
        # 他の必須フィールドも含まれることを確認
        required_fields = [
            'parts', 'hourly', 'total_planned', 'total_actual',
            'achievement_rate', 'remaining', 'last_updated'
        ]
        for field in required_fields:
            self.assertIn(field, data)
    
    @patch('production.utils.Result.objects.filter')
    def test_dashboard_template_renders_input_count(self, mock_result_filter):
        """ダッシュボードテンプレートが投入数を表示することのテスト"""
        # モック設定
        mock_result_filter.side_effect = self.mock_result_filter(count_target1=15, count_target2=25, count_non_target=8)
        
        # ダッシュボードページにアクセス
        url = reverse('production:dashboard', args=[self.line.id, self.test_date_str])
        response = self.client.get(url)
        
        # レスポンス検証
        self.assertEqual(response.status_code, 200)
        
        # テンプレートコンテキストに投入数が含まれることを確認
        self.assertIn('dashboard_data', response.context)
        dashboard_data = response.context['dashboard_data']
        self.assertIn('input_count', dashboard_data)
        
        # 投入数が正しく計算されることを確認
        expected_input_count = 15 + 25  # 投入数対象設備のみ
        self.assertEqual(dashboard_data['input_count'], expected_input_count)
        
        # HTMLに投入数カードが含まれることを確認
        self.assertContains(response, 'id="input-count"')
        self.assertContains(response, '投入数')
        self.assertContains(response, str(expected_input_count))
    
    @patch('production.utils.Result.objects.filter')
    def test_input_count_updates_with_result_changes(self, mock_result_filter):
        """実績変更時に投入数が更新されることのテスト"""
        # 初期モック設定
        mock_result_filter.side_effect = self.mock_result_filter(count_target1=10, count_target2=10, count_non_target=5)
        
        # 初期投入数確認
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        initial_input_count = dashboard_data['input_count']
        self.assertEqual(initial_input_count, 20)  # 10 + 10
        
        # 更新されたモック設定（新しい実績を追加）
        mock_result_filter.side_effect = self.mock_result_filter(count_target1=11, count_target2=10, count_non_target=5)
        
        # 投入数が更新されることを確認
        updated_dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        updated_input_count = updated_dashboard_data['input_count']
        self.assertEqual(updated_input_count, 21)  # 11 + 10
    
    @patch('production.utils.Result.objects.filter')
    def test_input_count_with_machine_configuration_changes(self, mock_result_filter):
        """設備設定変更時の投入数動作テスト"""
        # 初期モック設定
        mock_result_filter.side_effect = self.mock_result_filter(count_target1=12, count_target2=18, count_non_target=6)
        
        # 初期投入数確認
        initial_dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        initial_input_count = initial_dashboard_data['input_count']
        self.assertEqual(initial_input_count, 30)  # 12 + 18
        
        # 設備1を投入数対象から除外
        self.machine_target1.is_count_target = False
        self.machine_target1.save()
        
        # 投入数が更新されることを確認
        updated_dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        updated_input_count = updated_dashboard_data['input_count']
        self.assertEqual(updated_input_count, 18)  # 18のみ（設備1の12は除外）
        
        # 非投入数対象設備を投入数対象に変更
        self.machine_non_target.is_count_target = True
        self.machine_non_target.save()
        
        # 新しいモック設定（非投入数対象設備も含む）
        def new_filter_side_effect(**kwargs):
            mock_queryset = MagicMock()
            machine_names = kwargs.get('machine__in', [])
            total_count = 0
            
            if self.machine_target2.name in machine_names:
                total_count += 18
            if self.machine_non_target.name in machine_names:
                total_count += 6
            
            mock_queryset.count.return_value = total_count
            return mock_queryset
        
        mock_result_filter.side_effect = new_filter_side_effect
        
        # 投入数が再度更新されることを確認
        final_dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        final_input_count = final_dashboard_data['input_count']
        self.assertEqual(final_input_count, 24)  # 18 + 6
    
    @patch('production.utils.Result.objects.filter')
    def test_input_count_time_period_boundary(self, mock_result_filter):
        """投入数の時間期間境界テスト"""
        # 時間期間内の実績のみカウントされるようにモック設定
        def filter_side_effect(**kwargs):
            mock_queryset = MagicMock()
            
            # 時間期間フィルタを確認
            timestamp_gte = kwargs.get('timestamp__gte')
            timestamp_lt = kwargs.get('timestamp__lt')
            
            # 正しい時間期間（8:30-翌日8:30）内の実績のみカウント
            if timestamp_gte == '20250115083000' and timestamp_lt == '20250116083000':
                mock_queryset.count.return_value = 1  # 稼働時間内の実績のみ
            else:
                mock_queryset.count.return_value = 0
            
            return mock_queryset
        
        mock_result_filter.side_effect = filter_side_effect
        
        # 投入数確認（稼働時間内の実績のみカウントされる）
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        input_count = dashboard_data['input_count']
        self.assertEqual(input_count, 1)  # 稼働時間内の実績のみ
    
    @patch('production.utils.Result.objects.filter')
    def test_input_count_includes_all_judgments(self, mock_result_filter):
        """投入数が全判定（OK/NG）を含むことの統合テスト"""
        def filter_side_effect(**kwargs):
            mock_queryset = MagicMock()
            
            # 投入数計算（全判定を含む）- judgmentフィルタなし
            if 'judgment' not in kwargs:
                mock_queryset.count.return_value = 10  # OK 5個 + NG 5個 = 10個
            # 実績数計算（OKのみ）- judgment='1'
            elif kwargs.get('judgment') == '1':
                mock_queryset.count.return_value = 5  # OKのみ
            else:
                mock_queryset.count.return_value = 0
            
            return mock_queryset
        
        mock_result_filter.side_effect = filter_side_effect
        
        # 投入数確認（OK/NG両方がカウントされる）
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        input_count = dashboard_data['input_count']
        self.assertEqual(input_count, 10)  # OK 5個 + NG 5個 = 10個
        
        # 投入数と実績数が異なることを確認（実績数は0になる可能性があるため、投入数が大きいことを確認）
        total_actual = dashboard_data['total_actual']
        self.assertGreater(input_count, total_actual)  # 投入数 > 実績数
    
    def test_dashboard_api_error_handling(self):
        """ダッシュボードAPI エラーハンドリングテスト"""
        # 存在しないライン IDでAPIアクセス
        url = f'/production/api/dashboard-data/99999/{self.test_date_str}/'
        response = self.client.get(url)
        
        # 404エラーが返されることを確認
        self.assertEqual(response.status_code, 404)
    
    def test_dashboard_template_error_handling(self):
        """ダッシュボードテンプレート エラーハンドリングテスト"""
        # 存在しないライン IDでページアクセス
        url = reverse('production:dashboard', args=[99999, self.test_date_str])
        response = self.client.get(url)
        
        # 404エラーが返されることを確認
        self.assertEqual(response.status_code, 404)


class InputCountWorkCalendarIntegrationTest(TestCase):
    """投入数と稼働カレンダーの統合テスト"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        logging.disable(logging.WARNING)
        
        # テストユーザー作成
        self.user = User.objects.create_user(
            username='calendaruser',
            password='testpass',
            is_superuser=True
        )
        
        # テストライン作成
        self.line = Line.objects.create(
            name='カレンダーテストライン',
            is_active=True
        )
        
        # テスト設備作成
        self.machine = Machine.objects.create(
            name='カレンダー設備',
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        
        # テスト機種作成
        from production.models import Category
        category = Category.objects.create(name='カレンダーカテゴリ')
        self.part = Part.objects.create(
            name='カレンダー機種',
            line=self.line,
            category=category,
            target_pph=60
        )
        
        self.test_date = date(2025, 1, 15)
        self.test_date_str = '2025-01-15'
        
        self.client = Client()
        self.client.force_login(self.user)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        logging.disable(logging.NOTSET)
    
    @patch('production.utils.Result.objects.filter')
    def test_input_count_with_custom_work_start_time(self, mock_result_filter):
        """カスタム稼働開始時刻での投入数計算テスト"""
        # カスタム稼働開始時刻（10:00）の稼働カレンダー作成
        work_calendar = WorkCalendar.objects.create(
            line=self.line,
            work_start_time=time(10, 0),
            morning_meeting_duration=20
        )
        
        def filter_side_effect(**kwargs):
            mock_queryset = MagicMock()
            
            # カスタム稼働開始時刻（10:00）での時間期間フィルタを確認
            timestamp_gte = kwargs.get('timestamp__gte')
            timestamp_lt = kwargs.get('timestamp__lt')
            
            # 正しい時間期間（10:00-翌日10:00）内の実績のみカウント
            if timestamp_gte == '20250115100000' and timestamp_lt == '20250116100000':
                mock_queryset.count.return_value = 1  # 稼働開始後の実績のみ
            else:
                mock_queryset.count.return_value = 0
            
            return mock_queryset
        
        mock_result_filter.side_effect = filter_side_effect
        
        # 投入数確認（稼働開始後の実績のみカウント）
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        input_count = dashboard_data['input_count']
        self.assertEqual(input_count, 1)  # 稼働開始後の実績のみ
    
    @patch('production.utils.Result.objects.filter')
    def test_input_count_without_work_calendar(self, mock_result_filter):
        """稼働カレンダーなしでの投入数計算テスト（デフォルト値使用）"""
        # 稼働カレンダーを作成しない（デフォルト8:30使用）
        
        def filter_side_effect(**kwargs):
            mock_queryset = MagicMock()
            
            # デフォルト稼働開始時刻（8:30）での時間期間フィルタを確認
            timestamp_gte = kwargs.get('timestamp__gte')
            timestamp_lt = kwargs.get('timestamp__lt')
            
            # 正しい時間期間（8:30-翌日8:30）内の実績のみカウント
            if timestamp_gte == '20250115083000' and timestamp_lt == '20250116083000':
                mock_queryset.count.return_value = 1  # デフォルト稼働開始後の実績のみ
            else:
                mock_queryset.count.return_value = 0
            
            return mock_queryset
        
        mock_result_filter.side_effect = filter_side_effect
        
        # 投入数確認（デフォルト稼働開始8:30後の実績のみカウント）
        dashboard_data = get_dashboard_data(self.line.id, self.test_date_str)
        input_count = dashboard_data['input_count']
        self.assertEqual(input_count, 1)  # デフォルト稼働開始後の実績のみ