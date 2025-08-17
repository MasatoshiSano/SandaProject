# Celeryアプリケーションをインポート（条件付き）
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celeryがインストールされていない場合は無視
    __all__ = ()