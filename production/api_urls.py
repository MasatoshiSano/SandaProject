"""
Production API URLs

終了予測時刻関連のAPIエンドポイント定義
"""

from django.urls import path
from .api_views import ForecastAPIView, ForecastSettingsAPIView, forecast_json_view

app_name = 'production_api'

urlpatterns = [
    # 終了予測関連API
    path('forecast/<int:line_id>/<str:date_str>/', 
         ForecastAPIView.as_view(), 
         name='forecast-detail'),
    
    path('forecast/<int:line_id>/<str:date_str>/calculate/', 
         ForecastAPIView.as_view(), 
         name='forecast-calculate'),
    
    # 予測設定API
    path('forecast/settings/<int:line_id>/', 
         ForecastSettingsAPIView.as_view(), 
         name='forecast-settings'),
    
    # JSON取得API（CSRF例外対応）
    path('forecast/json/<int:line_id>/<str:date_str>/', 
         forecast_json_view, 
         name='forecast-json'),
]