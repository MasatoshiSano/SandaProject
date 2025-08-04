from django.urls import path, include
from . import views

app_name = 'production'

urlpatterns = [
    # ライン選択
    path('line-select/', views.LineSelectView.as_view(), name='line_select'),
    
    # ダッシュボード
    path('dashboard/<int:line_id>/<str:date>/', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/<int:line_id>/', views.DashboardView.as_view(), name='dashboard_today'),
    
    # 計画管理
    path('plan/<int:pk>/update/', views.PlanUpdateView.as_view(), name='plan_update'),
    path('plan/<int:pk>/delete/', views.PlanDeleteView.as_view(), name='plan_delete'),
    path('plan/<int:line_id>/<str:date>/', views.PlanListView.as_view(), name='plan_list'),
    path('plan/<int:line_id>/<str:date>/create/', views.PlanCreateView.as_view(), name='plan_create'),
    
    # 機種管理
    path('part/create/', views.PartCreateView.as_view(), name='part_create'),
    path('part/<int:pk>/update/', views.PartUpdateView.as_view(), name='part_update'),
    path('part/list/', views.PartListView.as_view(), name='part_list'),
    
    # カテゴリ・タグ管理
    path('category/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('tag/create/', views.TagCreateView.as_view(), name='tag_create'),
    
    # 実績管理
    path('result/<int:line_id>/', views.ResultListView.as_view(), name='result_list'),
    path('result/create/', views.ResultCreateView.as_view(), name='result_create'),
    path('result/<int:pk>/update/', views.ResultUpdateView.as_view(), name='result_update'),
    path('result/<int:pk>/delete/', views.ResultDeleteView.as_view(), name='result_delete'),
    
    # グラフ・分析
    path('graph/weekly/<int:line_id>/', views.WeeklyGraphView.as_view(), name='weekly_graph'),
    path('graph/monthly/<int:line_id>/', views.MonthlyGraphView.as_view(), name='monthly_graph'),
    
    # API (WebSocket用)
    path('api/dashboard-data/<int:line_id>/<str:date>/', views.DashboardDataAPIView.as_view(), name='dashboard_api'),
    path('api/graph-data/<int:line_id>/<str:period>/<str:date>/', views.GraphDataAPIView.as_view(), name='graph_api'),
    
    # 追加API（要件対応）
    path('api/part-info/<int:part_id>/', views.PartInfoAPIView.as_view(), name='part_info_api'),
    path('api/plan-info/<int:plan_id>/', views.PlanInfoAPIView.as_view(), name='plan_info_api'),
    path('api/plan-sequence-update/<int:line_id>/<str:date>/', views.PlanSequenceUpdateAPIView.as_view(), name='plan_sequence_update'),
    
    # 週別分析パフォーマンス改善API
    path('api/weekly-analysis/<int:line_id>/<str:date>/', views.WeeklyAnalysisAPIView.as_view(), name='weekly_analysis_api'),
    path('api/performance-metrics/<int:line_id>/<str:date>/', views.PerformanceMetricsAPIView.as_view(), name='performance_metrics_api'),
    
    # 監視とアラートAPI
    path('monitoring/health/', views.health_check_api, name='health_check'),
    path('monitoring/performance/', views.performance_stats_api, name='performance_stats'),
    path('monitoring/metrics/', views.aggregation_metrics_api, name='aggregation_metrics'),
    
    path('feedback/', views.FeedbackListView.as_view(), name='feedback_list'),
    path('feedback/submit/', views.feedback_submit, name='feedback_submit'),
    path('feedback/edit/<int:pk>/', views.feedback_edit, name='feedback_edit'),
    path('feedback/count/', views.get_new_feedback_count, name='feedback_count'),
    
    # 終了予測時刻API
    path('api/', include('production.api_urls')),
] 