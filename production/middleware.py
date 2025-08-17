import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """パフォーマンス監視ミドルウェア"""
    
    def process_request(self, request):
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # ダッシュボード関連のリクエストのみログ出力
            try:
                resolved = resolve(request.path_info)
                if 'dashboard' in resolved.url_name or 'dashboard' in str(resolved.view_name):
                    logger.info(
                        f"Dashboard Performance: {request.method} {request.path} "
                        f"- {duration*1000:.2f}ms - Status: {response.status_code}"
                    )
                    
                    # 遅いリクエストを警告
                    if duration > 5.0:  # 5秒以上
                        logger.warning(
                            f"Slow Dashboard Request: {request.path} took {duration:.2f}s"
                        )
                        
            except Exception:
                pass  # URL解決に失敗した場合は無視
        
        return response


class DashboardCacheMiddleware(MiddlewareMixin):
    """ダッシュボード専用キャッシュミドルウェア"""
    
    def process_request(self, request):
        # ダッシュボードページでキャッシュヘッダーを設定
        try:
            resolved = resolve(request.path_info)
            if 'dashboard' in resolved.url_name or 'dashboard' in str(resolved.view_name):
                # ダッシュボードページの場合、キャッシュ制御ヘッダーを設定
                request.is_dashboard = True
        except Exception:
            request.is_dashboard = False
        
        return None
    
    def process_response(self, request, response):
        if getattr(request, 'is_dashboard', False):
            # ダッシュボードページのレスポンスにキャッシュヘッダーを追加
            response['Cache-Control'] = 'private, max-age=60'  # 1分間キャッシュ
            response['Vary'] = 'Cookie'
        
        return response