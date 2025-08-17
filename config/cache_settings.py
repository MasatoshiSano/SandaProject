"""
キャッシュ設定の最適化

予測計算のパフォーマンス向上のための階層化キャッシュ設定
"""

# Redis キャッシュの階層化設定
CACHE_HIERARCHY = {
    # レベル1: 高速アクセス（短期間）
    'forecast_results': {
        'timeout': 900,  # 15分
        'key_prefix': 'forecast_',
        'description': '予測計算結果'
    },
    
    # レベル2: 中間データ（中期間）
    'actuals_data': {
        'timeout': 1800,  # 30分
        'key_prefix': 'actuals_',
        'description': '実績データ'
    },
    
    # レベル3: 基本データ（長期間）
    'basic_data': {
        'timeout': 21600,  # 6時間
        'key_prefix': 'basic_',
        'description': '計画・設定データ'
    },
    
    # レベル4: 設定データ（超長期間）
    'config_data': {
        'timeout': 86400,  # 24時間
        'key_prefix': 'config_',
        'description': 'ライン・カレンダー設定'
    }
}

# Oracle クエリ最適化設定
ORACLE_QUERY_OPTIMIZATION = {
    'max_batch_size': 100,  # IN句の最大サイズ
    'query_timeout': 30,    # クエリタイムアウト（秒）
    'connection_pool_size': 5,  # コネクションプール
    'enable_query_cache': True,  # クエリキャッシュ有効
}

# パフォーマンス監視設定
PERFORMANCE_MONITORING = {
    'enable_timing_logs': True,
    'slow_query_threshold': 1000,  # 1000ms以上を遅いクエリとみなす
    'cache_hit_rate_target': 0.8,  # キャッシュヒット率目標80%
}
