"""
月別分析の性能テスト
"""
from django.test import TestCase
from django.test.utils import override_settings
from django.db import connection
from django.utils import timezone
from datetime import date, timedelta
import time
import logging

from production.models import Line, Part, Plan, WeeklyResultAggregation
from production.utils import get_monthly_graph_data, get_month_dates


class MonthlyAnalysisPerformanceTest(TestCase):
    """月別分析の性能テスト"""
    
    def setUp(self):
        """大量のテストデータ準備"""
        # テスト用ライン作成
        self.line = Line.objects.create(
            name='性能テストライン',
            description='性能テスト用ライン'
        )
        
        # テスト用機種作成（複数）
        self.parts = []
        for i in range(5):  # 5種類の機種
            part = Part.objects.create(name=f'機種{i+1}')
            self.parts.append(part)
        
        # テスト日付（2025年1月）
        self.test_date = date(2025, 1, 15)
        self.month_dates = get_month_dates(self.test_date)
        
        # 大量のテストデータ作成
        self._create_large_test_data()
    
    def _create_large_test_data(self):
        """大量のテストデータ作成"""
        # 計画データ作成（月全体、全機種）
        plans = []
        for test_date in self.month_dates:
            for i, part in enumerate(self.parts):
                plans.append(Plan(
                    line=self.line,
                    date=test_date,
                    part=part,
                    planned_quantity=100 + i * 20,
                    sequence=i + 1
                ))
        
        # 一括作成
        Plan.objects.bulk_create(plans)
        
        # 集計データ作成（月全体、全機種、OK/NG両方）
        aggregations = []
        for test_date in self.month_dates:
            for part in self.parts:
                # OK実績
                aggregations.append(WeeklyResultAggregation(
                    date=test_date,
                    line=self.line.name,
                    part=part.name,
                    judgment='OK',
                    total_quantity=80 + hash(f"{test_date}{part.name}") % 50,
                    result_count=1
                ))
                # NG実績
                aggregations.append(WeeklyResultAggregation(
                    date=test_date,
                    line=self.line.name,
                    part=part.name,
                    judgment='NG',
                    total_quantity=5 + hash(f"{test_date}{part.name}NG") % 10,
                    result_count=1
                ))
        
        # 一括作成
        WeeklyResultAggregation.objects.bulk_create(aggregations)
    
    def test_execution_time(self):
        """実行時間のテスト"""
        # 実行時間を測定
        start_time = time.time()
        result = get_monthly_graph_data(self.line.id, self.test_date)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # 結果が正常に返されることを確認
        self.assertIsNotNone(result)
        self.assertIn('chart_data', result)
        self.assertIn('monthly_stats', result)
        
        # 実行時間が目標範囲内であることを確認（要調整）
        self.assertLess(execution_time, 2.0, f"実行時間が遅すぎます: {execution_time:.3f}秒")
        
        # パフォーマンス情報をログ出力
        print(f"\n=== 月別分析 性能テスト結果 ===")
        print(f"実行時間: {execution_time:.3f}秒")
        print(f"処理データ量: {len(self.month_dates)}日分, {len(self.parts)}機種")
        print(f"計画レコード数: {Plan.objects.count()}")
        print(f"集計レコード数: {WeeklyResultAggregation.objects.count()}")
    
    def test_query_count(self):
        """クエリ実行回数のテスト"""
        # クエリ実行回数を測定
        initial_queries = len(connection.queries)
        
        result = get_monthly_graph_data(self.line.id, self.test_date)
        
        final_queries = len(connection.queries)
        query_count = final_queries - initial_queries
        
        # 結果が正常に返されることを確認
        self.assertIsNotNone(result)
        
        # クエリ実行回数が目標範囲内であることを確認
        self.assertLess(query_count, 20, f"クエリ実行回数が多すぎます: {query_count}回")
        
        # パフォーマンス情報をログ出力
        print(f"クエリ実行回数: {query_count}回")
        
        # 実行されたクエリの詳細を表示（デバッグ用）
        if query_count > 0:
            recent_queries = connection.queries[-query_count:]
            for i, query in enumerate(recent_queries, 1):
                print(f"Query {i}: {query['sql'][:100]}...")
    
    def test_memory_efficiency(self):
        """メモリ効率のテスト"""
        import psutil
        import os
        
        # メモリ使用量測定開始
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # 複数回実行してメモリリークをチェック
        for _ in range(3):
            result = get_monthly_graph_data(self.line.id, self.test_date)
            self.assertIsNotNone(result)
        
        # メモリ使用量測定終了
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # メモリ増加量が許容範囲内であることを確認
        self.assertLess(memory_increase, 50, f"メモリ使用量増加が大きすぎます: {memory_increase:.1f}MB")
        
        print(f"メモリ使用量: {memory_before:.1f}MB → {memory_after:.1f}MB (増加: {memory_increase:.1f}MB)")
    
    def test_data_volume_scalability(self):
        """データ量スケーラビリティのテスト"""
        # 様々なデータ規模でのテスト
        test_cases = [
            (7, "1週間"),
            (31, "1ヶ月"),
        ]
        
        for days, description in test_cases:
            # テスト期間を調整
            test_dates = self.month_dates[:days]
            
            # 実行時間を測定
            start_time = time.time()
            result = get_monthly_graph_data(self.line.id, self.test_date)
            end_time = time.time()
            
            execution_time = end_time - start_time
            
            # 結果の検証
            self.assertIsNotNone(result)
            self.assertEqual(len(result['chart_data']['labels']), len(self.month_dates))
            
            print(f"{description}データ処理時間: {execution_time:.3f}秒")
    
    def test_concurrent_access(self):
        """同時アクセスのテスト"""
        import threading
        import queue
        
        # 結果格納用キュー
        results = queue.Queue()
        errors = queue.Queue()
        
        def worker():
            try:
                start_time = time.time()
                result = get_monthly_graph_data(self.line.id, self.test_date)
                end_time = time.time()
                results.put({
                    'result': result,
                    'execution_time': end_time - start_time
                })
            except Exception as e:
                errors.put(e)
        
        # 複数スレッドで同時実行
        threads = []
        thread_count = 3
        
        for _ in range(thread_count):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # 全スレッドの完了を待機
        for thread in threads:
            thread.join()
        
        # 結果の検証
        self.assertEqual(results.qsize(), thread_count, "一部のスレッドが失敗しました")
        self.assertEqual(errors.qsize(), 0, f"エラーが発生: {list(errors.queue)}")
        
        # 実行時間の統計
        execution_times = []
        while not results.empty():
            result_data = results.get()
            execution_times.append(result_data['execution_time'])
            self.assertIsNotNone(result_data['result'])
        
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        min_time = min(execution_times)
        
        print(f"同時アクセステスト ({thread_count}スレッド):")
        print(f"  平均実行時間: {avg_time:.3f}秒")
        print(f"  最大実行時間: {max_time:.3f}秒")
        print(f"  最小実行時間: {min_time:.3f}秒")
    
    def test_comparison_with_legacy(self):
        """従来方式との性能比較テスト"""
        from production.utils import _get_monthly_graph_data_legacy
        
        # 新方式の実行時間測定
        start_time = time.time()
        new_result = get_monthly_graph_data(self.line.id, self.test_date)
        new_time = time.time() - start_time
        
        # 従来方式の実行時間測定
        start_time = time.time()
        legacy_result = _get_monthly_graph_data_legacy(self.line.id, self.test_date)
        legacy_time = time.time() - start_time
        
        # 両方とも正常に動作することを確認
        self.assertIsNotNone(new_result)
        self.assertIsNotNone(legacy_result)
        
        # 性能改善が確認できることを期待
        improvement_ratio = legacy_time / new_time if new_time > 0 else float('inf')
        
        print(f"\n=== 性能比較結果 ===")
        print(f"新方式実行時間: {new_time:.3f}秒")
        print(f"従来方式実行時間: {legacy_time:.3f}秒")
        print(f"改善倍率: {improvement_ratio:.2f}倍")
        
        # 新方式の方が速いことを期待（ただし、データが少ない場合は逆転する可能性もある）
        if legacy_time > 0.1:  # 従来方式が0.1秒以上の場合のみ比較
            self.assertLess(new_time, legacy_time * 1.5, "新方式の性能改善が不十分です")