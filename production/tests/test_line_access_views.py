from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.http import JsonResponse
import json

from production.models import Line, UserLineAccess
from production.views import LineAccessConfigView, AdminUserAccessView


class LineAccessConfigViewTestCase(TestCase):
    """ライン アクセス設定ビューのテストケース"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        self.client = Client()
        
        # テストユーザーを作成
        self.regular_user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )
        
        # テストラインを作成
        self.line1 = Line.objects.create(
            name='Line A',
            description='Test Line A',
            is_active=True
        )
        self.line2 = Line.objects.create(
            name='Line B',
            description='Test Line B',
            is_active=True
        )
        self.inactive_line = Line.objects.create(
            name='Inactive Line',
            description='Inactive Test Line',
            is_active=False
        )
    
    def test_line_access_config_view_get_unauthenticated(self):
        """未認証ユーザーのアクセステスト"""
        url = reverse('production:line_access_config')
        response = self.client.get(url)
        
        # ログインページにリダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_line_access_config_view_get_authenticated(self):
        """認証済みユーザーのGETリクエストテスト"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('production:line_access_config')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ライン アクセス設定')
        self.assertContains(response, self.line1.name)
        self.assertContains(response, self.line2.name)
        # 非アクティブなラインは表示されない
        self.assertNotContains(response, self.inactive_line.name)
    
    def test_line_access_config_view_post_valid_data(self):
        """有効なデータでのPOSTリクエストテスト"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('production:line_access_config')
        
        data = {
            'line_ids': [self.line1.id, self.line2.id]
        }
        response = self.client.post(url, data)
        
        # line_selectページにリダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('production:line_select'))
        
        # ライン アクセス権限が作成されていることを確認
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 2)
        self.assertTrue(UserLineAccess.objects.filter(user=self.regular_user, line=self.line1).exists())
        self.assertTrue(UserLineAccess.objects.filter(user=self.regular_user, line=self.line2).exists())
    
    def test_line_access_config_view_post_empty_data(self):
        """空のデータでのPOSTリクエストテスト"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('production:line_access_config')
        
        # 既存のアクセス権限を作成
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        data = {'line_ids': []}
        response = self.client.post(url, data)
        
        # リダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
        
        # 既存のアクセス権限が削除されていることを確認
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 0)
    
    def test_line_access_config_view_admin_user(self):
        """管理者ユーザーのアクセステスト"""
        self.client.login(username='admin', password='adminpass123')
        url = reverse('production:line_access_config')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # 管理者の場合、現在のライン アクセス権限は空のリストになる
        self.assertIn('user_line_ids', response.context)


class LineAccessConfigAPITestCase(TestCase):
    """ライン アクセス設定API のテストケース"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        self.client = Client()
        
        # テストユーザーを作成
        self.regular_user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # テストラインを作成
        self.line1 = Line.objects.create(
            name='Line A',
            description='Test Line A',
            is_active=True
        )
        self.line2 = Line.objects.create(
            name='Line B',
            description='Test Line B',
            is_active=True
        )
    
    def test_line_access_api_get_unauthenticated(self):
        """未認証ユーザーのAPIアクセステスト"""
        url = reverse('production:line_access_config_api')
        response = self.client.get(url)
        
        # ログインページにリダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
    
    def test_line_access_api_get_authenticated(self):
        """認証済みユーザーのGET APIテスト"""
        self.client.login(username='testuser', password='testpass123')
        
        # ライン アクセス権限を作成
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        url = reverse('production:line_access_config_api')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn(self.line1.id, data['line_ids'])
        self.assertNotIn(self.line2.id, data['line_ids'])
    
    def test_line_access_api_post_valid_data(self):
        """有効なデータでのPOST APIテスト"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('production:line_access_config_api')
        
        data = {
            'line_ids': [self.line1.id, self.line2.id]
        }
        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        
        # ライン アクセス権限が作成されていることを確認
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 2)
    
    def test_line_access_api_post_invalid_method(self):
        """無効なHTTPメソッドのテスト"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('production:line_access_config_api')
        
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')


class AdminUserAccessViewTestCase(TestCase):
    """管理者用ユーザー アクセス管理ビューのテストケース"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        self.client = Client()
        
        # テストユーザーを作成
        self.regular_user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )
        
        # テストラインを作成
        self.line1 = Line.objects.create(
            name='Line A',
            description='Test Line A',
            is_active=True
        )
        self.line2 = Line.objects.create(
            name='Line B',
            description='Test Line B',
            is_active=True
        )
    
    def test_admin_user_access_view_unauthenticated(self):
        """未認証ユーザーのアクセステスト"""
        url = reverse('production:admin_user_access')
        response = self.client.get(url)
        
        # ログインページにリダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_admin_user_access_view_regular_user(self):
        """一般ユーザーのアクセステスト（権限なし）"""
        # ライン アクセス権限を作成（ミドルウェアのリダイレクトを回避）
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse('production:admin_user_access')
        response = self.client.get(url)
        
        # 403 Forbiddenが返されることを確認
        self.assertEqual(response.status_code, 403)
    
    def test_admin_user_access_view_admin_user(self):
        """管理者ユーザーのアクセステスト"""
        self.client.login(username='admin', password='adminpass123')
        url = reverse('production:admin_user_access')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ユーザー アクセス管理')
        self.assertContains(response, self.regular_user.username)
        # 管理者自身は一覧に表示されない（ユーザーカード内での確認）
        self.assertNotContains(response, f'data-user-id="{self.admin_user.id}"')


class AdminUserAccessAPITestCase(TestCase):
    """管理者用ユーザー アクセス管理API のテストケース"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        self.client = Client()
        
        # テストユーザーを作成
        self.regular_user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )
        
        # テストラインを作成
        self.line1 = Line.objects.create(
            name='Line A',
            description='Test Line A',
            is_active=True
        )
        self.line2 = Line.objects.create(
            name='Line B',
            description='Test Line B',
            is_active=True
        )
    
    def test_admin_user_access_api_regular_user(self):
        """一般ユーザーのAPIアクセステスト（権限なし）"""
        # ライン アクセス権限を作成（ミドルウェアのリダイレクトを回避）
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse('production:admin_user_access_api')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_admin_user_access_api_get_all_users(self):
        """全ユーザー情報取得のテスト"""
        self.client.login(username='admin', password='adminpass123')
        
        # ライン アクセス権限を作成
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        url = reverse('production:admin_user_access_api')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'testuser')
        self.assertEqual(data['users'][0]['line_count'], 1)
    
    def test_admin_user_access_api_get_specific_user(self):
        """特定ユーザー情報取得のテスト"""
        self.client.login(username='admin', password='adminpass123')
        
        # ライン アクセス権限を作成
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        url = reverse('production:admin_user_access_api')
        response = self.client.get(url, {'user_id': self.regular_user.id})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['username'], 'testuser')
        self.assertIn(self.line1.id, data['line_ids'])
    
    def test_admin_user_access_api_post_update_user_access(self):
        """ユーザー アクセス権限更新のテスト"""
        self.client.login(username='admin', password='adminpass123')
        url = reverse('production:admin_user_access_api')
        
        data = {
            'user_id': self.regular_user.id,
            'line_ids': [self.line1.id, self.line2.id]
        }
        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        
        # ライン アクセス権限が更新されていることを確認
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 2)
    
    def test_admin_user_access_api_post_invalid_user(self):
        """存在しないユーザーでの更新テスト"""
        self.client.login(username='admin', password='adminpass123')
        url = reverse('production:admin_user_access_api')
        
        data = {
            'user_id': 999,  # 存在しないID
            'line_ids': [self.line1.id]
        }
        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'error')