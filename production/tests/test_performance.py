"""
パフォーマンステスト
"""

import time
from datetime import date, timedelta
from django.test import TestCase, override_settings
from django.core.cache import cache
from production.models import Line, WeeklyResultAggregation
from production.services import WeeklyAnalysisService


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    DATABASE_ROUTERS=[],  # ルーターを無効化
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
)
class TestPerformanceOptimization(TestCase):
    """パフォーマンス最適化のテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        self.service = WeeklyAnalysisService()
        
        # テスト用ライン作成
        self.line = Line.objects.create(
            name="パフォーマンステストライン",
            description="パフォーマンステスト用"
        )
        
        # テスト用日付
        self.test_date = date(2025, 1, 15)
        self.week_start = self.test_date - timedelta(days=self.test_date.weekday())
        self.week_dates = [self.week_start + timedelta(days=i) for i in range(7)]
        
        # 大量のテストデータを作成
        self._create_large_test_data()
    
    def _create_large_test_data(self):
        """大量のテストデータを作成"""
        aggregations = []
        
        # 各日に複数の機種・設備のデータを作成
        for day in self.week_dates:
            for part_num in range(5):  # 5機種
                for machine_num in range(3):  # 3設備
                    for judgment in ['OK', 'NG']:
                        quantity = 100 if judgment == 'OK' else 5
                        count = 10 if judgment == 'OK' else 1
                        
                        aggregations.append(
                            WeeklyResultAggregation(
                                date=day,
                                line=self.line.name,
                                machine=f"機械{machine_num}",
                                part=f"製品{part_num}",
                                judgment=judgment,
                                total_quantity=quantity,
                                result_count=count
                            )
                        )
        
        # バルクインサートで効率的に作成
        WeeklyResultAggregation.objects.bulk_create(aggregations, batch_size=100)
    
    def test_query_optimization_performance(self):
        """クエリ最適化のパフォーマンステスト"""
        # キャッシュをクリア
        cache.clear()
        
        # 初回実行時間を測定
        start_time = time.time()
        result1 = self.service.get_weekly_data(self.line.id, self.test_date)
        first_execution_time = time.time() - start_time
        
        # 2回目実行時間を測定（キャッシュ効果を確認）
        start_time = time.time()
        result2 = self.service.get_weekly_data(self.line.id, self.test_date)
        second_execution_time = time.time() - start_time
        
        # 結果が同じであることを確認
        self.assertEqual(result1['line_name'], result2['line_name'])
        self.assertEqual(len(result1['weekly_data']), len(result2['weekly_data']))
        
        # キャッシュにより2回目が高速であることを確認
        self.assertLess(second_execution_time, first_execution_time)
        
        print(f"初回実行時間: {first_execution_time:.4f}秒")
        print(f"キャッシュ実行時間: {second_execution_time:.4f}秒")
        print(f"高速化率: {first_execution_time / second_execution_time:.2f}倍")
    
    def test_part_analysis_performance(self):
        """機種別分析のパフォーマンステスト"""
        # キャッシュをクリア
        cache.clear()
        
        # 実行時間を測定
        start_time = time.time()
        result = self.service.get_part_analysis(self.line.id, self.week_dates)
        execution_time = time.time() - start_time
        
        # 結果の妥当性を確認
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # 各機種データの構造を確認
        for part_data in result:
            self.assertIn('name', part_data)
            self.assertIn('total_quantity', part_data)
            self.assertIn('achievement_rate', part_data)
            self.assertIn('defect_rate', part_data)
        
        print(f"機種別分析実行時間: {execution_time:.4f}秒")
        print(f"分析機種数: {len(result)}機種")
    
    def test_performance_metrics_optimization(self):
        """パフォーマンス指標の最適化テスト"""
        # キャッシュをクリア
        cache.clear()
        
        # 実行時間を測定
        start_time = time.time()
        result = self.service.get_performance_metrics(self.line.id, self.week_dates)
        execution_time = time.time() - start_time
        
        # 結果の妥当性を確認
        expected_keys = [
            'total_production', 'total_defects', 'defect_rate', 'working_days',
            'daily_average', 'part_count', 'machine_count', 'production_stability',
            'total_operations', 'efficiency_score'
        ]
        
        for key in expected_keys:
            self.assertIn(key, result)
        
        # 数値の妥当性確認
        self.assertGreaterEqual(result['total_production'], 0)
        self.assertGreaterEqual(result['defect_rate'], 0)
        self.assertLessEqual(result['defect_rate'], 100)
        self.assertEqual(result['working_days'], 7)  # 7日分のデータがある
        self.assertEqual(result['part_count'], 5)    # 5機種のデータがある
        self.assertEqual(result['machine_count'], 3) # 3設備のデータがある
        
        print(f"パフォーマンス指標実行時間: {execution_time:.4f}秒")
        print(f"総生産数: {result['total_production']}")
        print(f"不良率: {result['defect_rate']:.2f}%")
    
    def test_cache_effectiveness(self):
        """キャッシュ効果のテスト"""
        # キャッシュをクリア
        cache.clear()
        
        # 複数回実行してキャッシュ効果を測定
        execution_times = []
        
        for i in range(3):
            start_time = time.time()
            result = self.service.get_weekly_data(self.line.id, self.test_date)
            execution_time = time.time() - start_time
            execution_times.append(execution_time)
            
            # 結果が一貫していることを確認
            self.assertIn('weekly_data', result)
            self.assertEqual(len(result['weekly_data']), 7)
        
        # 初回以降はキャッシュにより高速であることを確認
        self.assertLess(execution_times[1], execution_times[0])
        self.assertLess(execution_times[2], execution_times[0])
        
        print(f"実行時間: {execution_times}")
        print(f"キャッシュ効果: {execution_times[0] / execution_times[1]:.2f}倍高速化")
    
    def test_bulk_query_optimization(self):
        """一括クエリ最適化のテスト"""
        # 個別クエリと一括クエリの比較
        
        # 一括クエリ（最適化版）の実行時間
        start_time = time.time()
        optimized_result = self.service.get_part_analysis(self.line.id, self.week_dates)
        optimized_time = time.time() - start_time
        
        # 結果の妥当性確認
        self.assertGreater(len(optimized_result), 0)
        
        print(f"最適化クエリ実行時間: {optimized_time:.4f}秒")
        print(f"処理データ量: {WeeklyResultAggregation.objects.count()}レコード")
    
    def test_memory_usage_optimization(self):
        """メモリ使用量最適化のテスト"""
        import tracemalloc
        
        # メモリ使用量の測定開始
        tracemalloc.start()
        
        # 週別データ取得
        result = self.service.get_weekly_data(self.line.id, self.test_date)
        
        # メモリ使用量を取得
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # 結果の妥当性確認
        self.assertIn('weekly_data', result)
        
        print(f"現在のメモリ使用量: {current / 1024 / 1024:.2f} MB")
        print(f"ピークメモリ使用量: {peak / 1024 / 1024:.2f} MB")
        
        # メモリ使用量が合理的な範囲内であることを確認
        self.assertLess(peak, 50 * 1024 * 1024)  # 50MB未満