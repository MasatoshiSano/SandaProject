"""
Celery設定

非同期タスク処理のためのCelery設定
"""

import os

try:
    from celery import Celery
    from celery.schedules import crontab
    
    # Django設定モジュールを指定
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
    
    app = Celery('sandaproject')
    
except ImportError:
    # Celeryがインストールされていない場合のダミー
    class DummyCelery:
        def config_from_object(self, *args, **kwargs):
            pass
        def autodiscover_tasks(self):
            pass
        @property
        def conf(self):
            return self
        def update(self, **kwargs):
            pass
        def task(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    app = DummyCelery()
    
    def crontab(*args, **kwargs):
        return None
    
    def debug_task(self):
        pass
    
    # 早期リターン
    if True:
        # Django設定からCelery設定を読み込み
        app.config_from_object('django.conf:settings', namespace='CELERY')
        
        # タスクの自動検出
        app.autodiscover_tasks()
        
        # Celery設定
        app.conf.update(
            # ブローカー設定
            broker_url=f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/0",
            result_backend=f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/0",
            
            # タスク設定
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='Asia/Tokyo',
            enable_utc=True,
            
            # ワーカー設定
            worker_prefetch_multiplier=1,
            task_acks_late=True,
            worker_max_tasks_per_child=1000,
            
            # 結果の保持期間
            result_expires=3600,  # 1時間
            
            # 定期タスク設定
            beat_schedule={
                'update-forecasts-every-15min': {
                    'task': 'production.tasks.update_optimized_forecasts_task',
                    'schedule': 900.0,  # 15分間隔
                },
                'clear-old-cache-hourly': {
                    'task': 'production.tasks.clear_old_cache_task',
                    'schedule': 3600.0,  # 1時間間隔
                },
                # 朝のウォームアップタスクを削除（不要）
            },
            beat_schedule_filename='celerybeat-schedule',
        )


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')