from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # 既存のダッシュボード用WebSocket
    re_path(r'ws/dashboard/(?P<line_id>\d+)/(?P<date>\d{4}-\d{2}-\d{2})/$', consumers.DashboardConsumer.as_asgi()),
    
    # 週別分析専用WebSocket
    re_path(r'ws/weekly-analysis/(?P<line_id>\d+)/$', consumers.WeeklyAnalysisConsumer.as_asgi()),
    
    # 集計状況監視用WebSocket
    re_path(r'ws/aggregation-status/$', consumers.AggregationStatusConsumer.as_asgi()),
]