from django.test import TestCase
from django.contrib.auth.models import User
from production.models import Line, UserLineAccess
from production.utils import has_line_access, get_user_line_access, update_user_line_access


class LineAccessUtilsTestCase(TestCase):
    """ライン アクセス ユーティリティ関数のテストケース"""
    
    def setUp(self):
        """テストデータのセットアップ"""
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
    
    def test_has_line_access_regular_user_no_access(self):
        """一般ユーザーがライン アクセス権限を持たない場合のテスト"""
        self.assertFalse(has_line_access(self.regular_user))
    
    def test_has_line_access_regular_user_with_access(self):
        """一般ユーザーがライン アクセス権限を持つ場合のテスト"""
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        self.assertTrue(has_line_access(self.regular_user))
    
    def test_has_line_access_admin_user(self):
        """管理者ユーザーは常にアクセス権限を持つことのテスト"""
        self.assertTrue(has_line_access(self.admin_user))
    
    def test_get_user_line_access_regular_user_no_access(self):
        """一般ユーザーがアクセス権限を持たない場合のライン取得テスト"""
        lines = get_user_line_access(self.regular_user)
        self.assertEqual(lines.count(), 0)
    
    def test_get_user_line_access_regular_user_with_access(self):
        """一般ユーザーがアクセス権限を持つ場合のライン取得テスト"""
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        UserLineAccess.objects.create(user=self.regular_user, line=self.line2)
        
        lines = get_user_line_access(self.regular_user)
        self.assertEqual(lines.count(), 2)
        self.assertIn(self.line1, lines)
        self.assertIn(self.line2, lines)
    
    def test_get_user_line_access_admin_user(self):
        """管理者ユーザーは全てのアクティブなラインにアクセス可能なことのテスト"""
        lines = get_user_line_access(self.admin_user)
        self.assertEqual(lines.count(), 2)  # アクティブなラインのみ
        self.assertIn(self.line1, lines)
        self.assertIn(self.line2, lines)
        self.assertNotIn(self.inactive_line, lines)
    
    def test_update_user_line_access_create_new(self):
        """新しいライン アクセス権限の作成テスト"""
        line_ids = [self.line1.id, self.line2.id]
        result = update_user_line_access(self.regular_user, line_ids)
        
        self.assertTrue(result)
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 2)
        self.assertTrue(UserLineAccess.objects.filter(user=self.regular_user, line=self.line1).exists())
        self.assertTrue(UserLineAccess.objects.filter(user=self.regular_user, line=self.line2).exists())
    
    def test_update_user_line_access_update_existing(self):
        """既存のライン アクセス権限の更新テスト"""
        # 初期アクセス権限を設定
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        
        # 異なるラインに更新
        line_ids = [self.line2.id]
        result = update_user_line_access(self.regular_user, line_ids)
        
        self.assertTrue(result)
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 1)
        self.assertFalse(UserLineAccess.objects.filter(user=self.regular_user, line=self.line1).exists())
        self.assertTrue(UserLineAccess.objects.filter(user=self.regular_user, line=self.line2).exists())
    
    def test_update_user_line_access_remove_all(self):
        """全てのライン アクセス権限の削除テスト"""
        # 初期アクセス権限を設定
        UserLineAccess.objects.create(user=self.regular_user, line=self.line1)
        UserLineAccess.objects.create(user=self.regular_user, line=self.line2)
        
        # 空のリストで更新（全削除）
        result = update_user_line_access(self.regular_user, [])
        
        self.assertTrue(result)
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 0)
    
    def test_update_user_line_access_invalid_line_ids(self):
        """無効なライン IDでの更新テスト"""
        invalid_line_ids = [999, 1000]  # 存在しないID
        result = update_user_line_access(self.regular_user, invalid_line_ids)
        
        self.assertTrue(result)  # エラーは発生しないが、何も作成されない
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 0)
    
    def test_update_user_line_access_inactive_line(self):
        """非アクティブなラインでの更新テスト"""
        line_ids = [self.inactive_line.id]
        result = update_user_line_access(self.regular_user, line_ids)
        
        self.assertTrue(result)  # エラーは発生しないが、非アクティブなラインは無視される
        self.assertEqual(UserLineAccess.objects.filter(user=self.regular_user).count(), 0)
    
    def test_update_user_line_access_admin_user(self):
        """管理者ユーザーの場合は更新されないことのテスト"""
        line_ids = [self.line1.id]
        result = update_user_line_access(self.admin_user, line_ids)
        
        self.assertTrue(result)
        # 管理者の場合はUserLineAccessレコードは作成されない
        self.assertEqual(UserLineAccess.objects.filter(user=self.admin_user).count(), 0)