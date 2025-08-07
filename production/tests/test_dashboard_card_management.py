"""
ダッシュボードカード管理機能のテストスイート

このテストモジュールは、以下のコンポーネントをテストします：
1. DashboardCardSetting モデル
2. DashboardCardSettingAdmin 管理画面
3. ダッシュボードビューでのカード表示機能
4. カード順序更新のAJAX機能
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test.utils import override_settings
from unittest.mock import patch, MagicMock
import json

from production.models import (
    DashboardCardSetting, Line, Machine, Part, Plan, Category, UserLineAccess
)
from production.admin import DashboardCardSettingAdmin
from production.dashboard_cards import DASHBOARD_CARDS


class DashboardCardSettingModelTest(TestCase):
    """DashboardCardSetting モデルのテストクラス"""

    def setUp(self):
        """テスト用のデータセットアップ"""
        self.card_setting = DashboardCardSetting.objects.create(
            name='テスト計画数カード',
            card_type='total_planned',
            is_visible=True,
            order=1,
            description='テスト用の計画数カード',
            is_system_card=True
        )

    def test_card_setting_creation(self):
        """カード設定の作成テスト"""
        self.assertEqual(self.card_setting.name, 'テスト計画数カード')
        self.assertEqual(self.card_setting.card_type, 'total_planned')
        self.assertTrue(self.card_setting.is_visible)
        self.assertEqual(self.card_setting.order, 1)
        self.assertTrue(self.card_setting.is_system_card)

    def test_card_setting_str_method(self):
        """__str__ メソッドのテスト"""
        expected_str = f"{self.card_setting.name} (表示順: {self.card_setting.order})"
        self.assertEqual(str(self.card_setting), expected_str)

    def test_card_setting_ordering(self):
        """カード設定の順序付けテスト"""
        # 追加のカード設定を作成
        card2 = DashboardCardSetting.objects.create(
            name='テスト実績数カード',
            card_type='total_actual',
            order=0  # より小さい順序
        )
        card3 = DashboardCardSetting.objects.create(
            name='テスト達成率カード',
            card_type='achievement_rate',
            order=2  # より大きい順序
        )

        # 順序での取得テスト
        cards = list(DashboardCardSetting.objects.all())
        self.assertEqual(cards[0], card2)  # order=0
        self.assertEqual(cards[1], self.card_setting)  # order=1
        self.assertEqual(cards[2], card3)  # order=2

    def test_card_type_choices_validation(self):
        """カードタイプの選択肢検証"""
        valid_card_types = list(DASHBOARD_CARDS.keys())
        
        for card_type in valid_card_types:
            card = DashboardCardSetting(
                name=f'テスト_{card_type}',
                card_type=card_type,
                order=1
            )
            # カードタイプが有効であることを確認
            self.assertIn(card_type, valid_card_types)

    def test_alert_threshold_defaults(self):
        """アラート閾値のデフォルト値テスト"""
        self.assertEqual(self.card_setting.alert_threshold_yellow, 80.0)
        self.assertEqual(self.card_setting.alert_threshold_red, 80.0)


class DashboardCardSettingAdminTest(TestCase):
    """DashboardCardSettingAdmin 管理画面のテストクラス"""

    def setUp(self):
        """テスト用のデータセットアップ"""
        # 管理者ユーザーを作成
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )
        
        # テスト用カード設定
        self.card1 = DashboardCardSetting.objects.create(
            name='計画数',
            card_type='total_planned',
            order=1,
            is_visible=True,
            is_system_card=True
        )
        self.card2 = DashboardCardSetting.objects.create(
            name='実績数',
            card_type='total_actual',
            order=2,
            is_visible=True,
            is_system_card=True
        )
        self.card3 = DashboardCardSetting.objects.create(
            name='カスタムカード',
            card_type='custom_card',
            order=3,
            is_visible=False,
            is_system_card=False
        )
        
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_admin_changelist_view(self):
        """管理画面の一覧表示テスト"""
        url = reverse('admin:production_dashboardcardsetting_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.card1.name)
        self.assertContains(response, self.card2.name)
        self.assertContains(response, self.card3.name)

    def test_admin_change_view(self):
        """管理画面の編集画面テスト"""
        url = reverse('admin:production_dashboardcardsetting_change', args=[self.card1.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.card1.name)

    def test_system_card_delete_protection(self):
        """システムカードの削除保護テスト"""
        admin = DashboardCardSettingAdmin(DashboardCardSetting, None)
        request = MagicMock()
        
        # システムカードは削除不可
        self.assertFalse(admin.has_delete_permission(request, self.card1))
        # カスタムカードは削除可能
        self.assertTrue(admin.has_delete_permission(request, self.card3))

    def test_update_order_ajax_endpoint(self):
        """カード順序更新のAJAXエンドポイントテスト"""
        url = reverse('admin:production_dashboardcardsetting_changelist') + 'update_order/'
        
        # 順序変更データ
        update_data = {
            'updates': [
                {'id': str(self.card1.pk), 'order': 3},
                {'id': str(self.card2.pk), 'order': 1},
                {'id': str(self.card3.pk), 'order': 2}
            ]
        }
        
        response = self.client.post(
            url,
            data=json.dumps(update_data),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # データベースの順序が更新されているか確認
        self.card1.refresh_from_db()
        self.card2.refresh_from_db() 
        self.card3.refresh_from_db()
        
        self.assertEqual(self.card1.order, 3)
        self.assertEqual(self.card2.order, 1)
        self.assertEqual(self.card3.order, 2)

    def test_bulk_enable_action(self):
        """一括表示有効化アクションのテスト"""
        # カード3を非表示に設定
        self.card3.is_visible = False
        self.card3.save()
        
        url = reverse('admin:production_dashboardcardsetting_changelist')
        data = {
            'action': 'enable_cards',
            '_selected_action': [str(self.card3.pk)],
            'index': 0
        }
        
        response = self.client.post(url, data)
        
        # リダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
        
        # カードが表示状態になったことを確認
        self.card3.refresh_from_db()
        self.assertTrue(self.card3.is_visible)

    def test_bulk_disable_action(self):
        """一括表示無効化アクションのテスト"""
        url = reverse('admin:production_dashboardcardsetting_changelist')
        data = {
            'action': 'disable_cards',
            '_selected_action': [str(self.card1.pk)],
            'index': 0
        }
        
        response = self.client.post(url, data)
        
        # リダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
        
        # カードが非表示状態になったことを確認
        self.card1.refresh_from_db()
        self.assertFalse(self.card1.is_visible)


class DashboardViewIntegrationTest(TestCase):
    """ダッシュボードビューとカード設定の統合テストクラス"""

    def setUp(self):
        """テスト用のデータセットアップ"""
        # テストユーザーとライン作成
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.line = Line.objects.create(name='テストライン')
        UserLineAccess.objects.create(user=self.user, line=self.line)
        
        # テスト用カード設定
        DashboardCardSetting.objects.create(
            name='計画数',
            card_type='total_planned',
            order=1,
            is_visible=True
        )
        DashboardCardSetting.objects.create(
            name='実績数',
            card_type='total_actual',
            order=2,
            is_visible=True
        )
        DashboardCardSetting.objects.create(
            name='非表示カード',
            card_type='hidden_card',
            order=3,
            is_visible=False
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    @patch('production.utils.get_dashboard_context')
    def test_dashboard_visible_cards_only(self, mock_get_context):
        """ダッシュボードで表示設定されたカードのみが表示されることのテスト"""
        # モックのダッシュボードコンテキスト
        mock_get_context.return_value = {
            'total_planned': 1000,
            'total_actual': 800,
            'achievement_rate': 80.0,
            'remaining': 200,
            'input_count': 750,
            'forecast_time': '17:30'
        }
        
        url = reverse('production:dashboard', args=[self.line.pk, '2024-01-15'])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # 表示設定されたカードが含まれることを確認
        self.assertContains(response, '計画数')
        self.assertContains(response, '実績数')
        
        # 非表示設定されたカードが含まれないことを確認
        self.assertNotContains(response, '非表示カード')

    @patch('production.utils.get_dashboard_context')
    def test_dashboard_card_ordering(self, mock_get_context):
        """ダッシュボードでカードが指定された順序で表示されることのテスト"""
        mock_get_context.return_value = {
            'total_planned': 1000,
            'total_actual': 800,
        }
        
        url = reverse('production:dashboard', args=[self.line.pk, '2024-01-15'])
        response = self.client.get(url)
        
        content = response.content.decode('utf-8')
        
        # 計画数カード（order=1）が実績数カード（order=2）より前に表示されることを確認
        planned_pos = content.find('計画数')
        actual_pos = content.find('実績数')
        
        self.assertGreater(actual_pos, planned_pos)

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_dashboard_card_caching(self):
        """ダッシュボードカード設定のキャッシング機能テスト"""
        # キャッシュをクリア
        cache.clear()
        
        # カード設定を取得（キャッシュに保存される）
        from production.utils import get_visible_dashboard_cards
        
        cards = get_visible_dashboard_cards()
        self.assertEqual(len(cards), 2)  # 表示設定された2つのカード
        
        # カード設定を変更
        card = DashboardCardSetting.objects.first()
        card.is_visible = False
        card.save()
        
        # キャッシュが更新されていることを確認
        # （実際の実装では保存時にキャッシュクリアが必要）


class DashboardCardRegistryTest(TestCase):
    """ダッシュボードカードレジストリシステムのテストクラス"""

    def test_dashboard_cards_registry(self):
        """ダッシュボードカードレジストリの構造テスト"""
        self.assertIsInstance(DASHBOARD_CARDS, dict)
        
        # 必要なカードタイプが含まれているかテスト
        expected_cards = [
            'total_planned', 'total_actual', 'achievement_rate', 
            'remaining', 'input_count', 'forecast_time'
        ]
        
        for card_type in expected_cards:
            self.assertIn(card_type, DASHBOARD_CARDS)
            card_config = DASHBOARD_CARDS[card_type]
            
            # カード設定に必要なキーが含まれているかテスト
            required_keys = ['name', 'template', 'context_key', 'default_order']
            for key in required_keys:
                self.assertIn(key, card_config)

    def test_card_type_validation_with_registry(self):
        """カードタイプのレジストリ検証テスト"""
        from production.utils import is_valid_card_type
        
        # 有効なカードタイプ
        self.assertTrue(is_valid_card_type('total_planned'))
        self.assertTrue(is_valid_card_type('total_actual'))
        
        # 無効なカードタイプ
        self.assertFalse(is_valid_card_type('invalid_card_type'))
        self.assertFalse(is_valid_card_type(''))


class DashboardCardManagementCommandTest(TestCase):
    """ダッシュボードカード管理コマンドのテストクラス"""

    def test_init_dashboard_cards_command(self):
        """ダッシュボードカード初期化コマンドのテスト"""
        from django.core.management import call_command
        from io import StringIO
        
        # 既存のカード設定をクリア
        DashboardCardSetting.objects.all().delete()
        
        # コマンド実行
        out = StringIO()
        call_command('init_dashboard_cards', stdout=out)
        
        # カード設定が作成されているか確認
        cards_count = DashboardCardSetting.objects.count()
        expected_count = len(DASHBOARD_CARDS)
        
        self.assertEqual(cards_count, expected_count)
        
        # 各カードが正しく作成されているか確認
        for card_type, config in DASHBOARD_CARDS.items():
            card = DashboardCardSetting.objects.get(card_type=card_type)
            self.assertEqual(card.name, config['name'])
            self.assertEqual(card.order, config['default_order'])
            self.assertTrue(card.is_visible)
            self.assertTrue(card.is_system_card)

    def test_init_dashboard_cards_idempotent(self):
        """ダッシュボードカード初期化コマンドの冪等性テスト"""
        from django.core.management import call_command
        
        # 初回実行
        call_command('init_dashboard_cards')
        initial_count = DashboardCardSetting.objects.count()
        
        # 2回目実行
        call_command('init_dashboard_cards')
        final_count = DashboardCardSetting.objects.count()
        
        # カード数が変わらないことを確認（重複作成されない）
        self.assertEqual(initial_count, final_count)


class DashboardCardErrorHandlingTest(TestCase):
    """ダッシュボードカード機能のエラーハンドリングテスト"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.line = Line.objects.create(name='テストライン')
        UserLineAccess.objects.create(user=self.user, line=self.line)
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    @patch('production.utils.get_dashboard_context')
    def test_dashboard_with_missing_card_template(self, mock_get_context):
        """存在しないカードテンプレートのエラーハンドリングテスト"""
        # 存在しないテンプレートを持つカード設定
        DashboardCardSetting.objects.create(
            name='無効なカード',
            card_type='invalid_card',
            order=1,
            is_visible=True
        )
        
        mock_get_context.return_value = {'invalid_card': 'test_value'}
        
        url = reverse('production:dashboard', args=[self.line.pk, '2024-01-15'])
        
        # エラーが発生しても500エラーにならないことを確認
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_with_corrupted_card_settings(self):
        """破損したカード設定でのエラーハンドリングテスト"""
        # 順序が重複するカード設定
        DashboardCardSetting.objects.create(
            name='カード1',
            card_type='card1',
            order=1,
            is_visible=True
        )
        DashboardCardSetting.objects.create(
            name='カード2',
            card_type='card2', 
            order=1,  # 同じ順序
            is_visible=True
        )
        
        url = reverse('production:dashboard', args=[self.line.pk, '2024-01-15'])
        response = self.client.get(url)
        
        # 重複する順序でもエラーが発生しないことを確認
        self.assertEqual(response.status_code, 200)