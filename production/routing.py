from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/dashboard/(?P<line_id>\d+)/(?P<date>\d{4}-\d{2}-\d{2})/$', consumers.DashboardConsumer.as_asgi()),
] 