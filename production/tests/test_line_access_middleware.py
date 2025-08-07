from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User, AnonymousUser
from django.http import HttpResponse
from django.urls import reverse

from production.models import Line, UserLineAccess
from production.middleware import LineAccessRedirectMiddleware


class LineAccessRedirectMiddlewareTestCase(TestCase):
    """ライン アクセス リダイレクト ミドルウェアのテストケース"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        self.factory = RequestFactory()
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
        
        # ミドルウェアインスタンスを作成
        def get_response(request):
            return HttpResponse('OK')
        
        self.middleware = LineAccessRedirectMiddleware(get_response)
    
    def test_middleware_anonymous_user(self):
        """未認証ユーザーはリダイレクトされないことのテスト"""
        request = self.factory.get('/production/dashboard/1/2025-01-01/')
        request.user = AnonymousUser()
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # リダイレクトされない
    
    def test_middleware_admin_user(self):
        """管理者ユーザーはリダイレクトされないことのテスト"""
        request = self.factory.get('/production/dashboard/1/2025-01-01/')
        request.user = self.admin_user
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # リダイレクトされない
    
    def test_middleware_user_with_line_access(self):
        """ライン アクセス権限を持つユーザーはリダイレクトされないことのテスト"""
        # ライン アクセス権限を作成
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        request = self.factory.get('/production/dashboard/1/2025-01-01/')
        request.user = self.regular_user
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # リダイレクトされない
    
    def test_middleware_user_without_line_access(self):
        """ライン アクセス権限を持たないユーザーはリダイレクトされることのテスト"""
        request = self.factory.get('/production/dashboard/1/2025-01-01/')
        request.user = self.regular_user
        
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)  # リダイレクトされる
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('production:line_access_config'))
    
    def test_middleware_excluded_paths(self):
        """除外パスではリダイレクトされないことのテスト"""
        excluded_paths = [
            '/production/line-access-config/',
            '/production/api/line-access-config/',
            '/accounts/logout/',
            '/admin/',
            '/static/css/style.css',
            '/media/image.jpg',
        ]
        
        for path in excluded_paths:
            request = self.factory.get(path)
            request.user = self.regular_user
            
            response = self.middleware.process_request(request)
            self.assertIsNone(response, f'Path {path} should be excluded')
    
    def test_middleware_excluded_patterns(self):
        """除外パターンではリダイレクトされないことのテスト"""
        excluded_patterns = [
            '/accounts/login/',
            '/accounts/signup/',
            '/api/some-endpoint/',
            '/admin/production/line/',
        ]
        
        for path in excluded_patterns:
            request = self.factory.get(path)
            request.user = self.regular_user
            
            response = self.middleware.process_request(request)
            self.assertIsNone(response, f'Path {path} should be excluded by pattern')
    
    def test_middleware_ajax_requests(self):
        """AJAXリクエストはリダイレクトされないことのテスト"""
        request = self.factory.get('/production/dashboard/1/2025-01-01/')
        request.user = self.regular_user
        request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # AJAXリクエストはリダイレクトされない
    
    def test_middleware_line_access_config_page(self):
        """ライン アクセス設定ページ自体はリダイレクトされないことのテスト"""
        request = self.factory.get('/production/line-access-config/')
        request.user = self.regular_user
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # 設定ページ自体はリダイレクトされない
    
    def test_middleware_integration_with_client(self):
        """Clientを使った統合テスト"""
        # ライン アクセス権限を持たないユーザーでログイン
        self.client.login(username='testuser', password='testpass123')
        
        # 機種一覧ページにアクセス（ミドルウェアが動作するページ）
        response = self.client.get('/production/part/list/')
        
        # ライン アクセス設定ページにリダイレクトされることを確認
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('production:line_access_config'))
    
    def test_middleware_integration_after_line_access_setup(self):
        """ライン アクセス設定後の統合テスト"""
        # ライン アクセス権限を作成
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        # ユーザーでログイン
        self.client.login(username='testuser', password='testpass123')
        
        # ダッシュボードにアクセス
        response = self.client.get('/production/line-select/')
        
        # 正常にアクセスできることを確認（リダイレクトされない）
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_is_excluded_path_method(self):
        """_is_excluded_pathメソッドの単体テスト"""
        # 完全一致のテスト
        self.assertTrue(self.middleware._is_excluded_path('/production/line-access-config/'))
        self.assertTrue(self.middleware._is_excluded_path('/admin/'))
        
        # パターン一致のテスト
        self.assertTrue(self.middleware._is_excluded_path('/accounts/login/'))
        self.assertTrue(self.middleware._is_excluded_path('/api/some-endpoint/'))
        
        # 除外されないパスのテスト
        self.assertFalse(self.middleware._is_excluded_path('/production/dashboard/1/2025-01-01/'))
        self.assertFalse(self.middleware._is_excluded_path('/production/plan/1/2025-01-01/'))
    
    def test_middleware_redirect_loop_prevention(self):
        """リダイレクトループの防止テスト"""
        # ライン アクセス設定ページにアクセス権限なしでアクセス
        request = self.factory.get('/production/line-access-config/')
        request.user = self.regular_user
        
        response = self.middleware.process_request(request)
        # 設定ページ自体は除外されているため、リダイレクトされない
        self.assertIsNone(response)
    
    def test_middleware_post_request(self):
        """POSTリクエストでのテスト"""
        request = self.factory.post('/production/plan/1/2025-01-01/create/')
        request.user = self.regular_user
        
        response = self.middleware.process_request(request)
        # POSTリクエストでもリダイレクトされる
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
    
    def test_middleware_with_session(self):
        """セッション付きリクエストでのテスト"""
        # セッションエンジンを設定
        from django.conf import settings
        from django.contrib.sessions.backends.db import SessionStore
        
        request = self.factory.get('/production/dashboard/1/2025-01-01/')
        request.user = self.regular_user
        request.session = SessionStore()
        
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)