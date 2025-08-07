from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from .utils import has_line_access


class LineAccessRedirectMiddleware:
    """
    ライン アクセス権限チェック用ミドルウェア
    
    ログイン済みユーザーがライン アクセス権限を持たない場合、
    自動的にライン アクセス設定ページにリダイレクトする
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # リダイレクト対象外のパス
        self.excluded_paths = [
            '/production/line-access-config/',
            '/production/api/line-access-config/',
            '/accounts/logout/',
            '/admin/',
            '/static/',
            '/media/',
        ]
        
        # リダイレクト対象外のパスパターン（部分一致）
        self.excluded_patterns = [
            '/accounts/',  # allauth関連
            '/api/',       # API関連（一部除く）
            '/admin/',     # Django管理画面
        ]
    
    def __call__(self, request):
        # リクエスト前の処理
        response = self.process_request(request)
        if response:
            return response
        
        # ビューの処理
        response = self.get_response(request)
        
        return response
    
    def process_request(self, request):
        """リクエスト処理前のチェック"""
        
        # 未認証ユーザーはスキップ
        if isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
            return None
        
        # 管理者はスキップ
        if request.user.is_superuser:
            return None
        
        # 除外パスのチェック
        if self._is_excluded_path(request.path):
            return None
        
        # AJAXリクエストはスキップ
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return None
        
        # ライン アクセス権限をチェック
        if not has_line_access(request.user):
            # ライン アクセス設定ページにリダイレクト
            return redirect('production:line_access_config')
        
        return None
    
    def _is_excluded_path(self, path):
        """除外パスかどうかをチェック"""
        
        # 完全一致チェック
        if path in self.excluded_paths:
            return True
        
        # パターン一致チェック
        for pattern in self.excluded_patterns:
            if path.startswith(pattern):
                return True
        
        # 静的ファイルとメディアファイルのチェック
        if path.startswith('/static/') or path.startswith('/media/'):
            return True
        
        return False