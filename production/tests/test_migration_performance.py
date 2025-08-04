"""
マイグレーションパフォーマンステスト
"""

import time
import logging
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from django.core.management import call_command
from django.test.utils import override_settings
from production.models import Result, WeeklyResultAggregation, Line
from datetime import date, datetime, timedelta
import tempfile
import os

logger = logging.getLogger(__name__)


class MigrationPerformanceTest(TransactionTestCase):
    """
    マイグレーションのパフォーマンステスト
    """
    databases = ['default']
    
    def setUp(self):
        """テストデータの準備"""
        # テスト用ラインを作成
        self.test_line = Line.objects.create(
            name='TEST_LINE',
            is_active=True
        )
        
        # テスト用実績データを作成
        self.create_test_result_data()
    
    def create_test_result_data(self):
        """テスト用の実績データを作成"""
        test_data = []
        base_date = date.today() - timedelta(days=30)
        
        # 30日分のテストデータを作成
        for day_offset in range(30):
            test_date = base_date + timedelta(days=day_offset)
            
            # 各日に複数の実績を作成
            for hour in range(8, 17):  # 8時から16時まで
                for machine in ['M01', 'M02']:
                    for part in ['Part-A', 'Part-B']:
                        for judgment in ['OK', 'NG']:
                            quantity = 10 if judgment == 'OK' else 2
                            
                            result = Result(
                                line=self.test_line.name,
                                machine=f'TEST_LINE-{machine}',
                                part=part,
                                judgment=judgment,
                                quantity=quantity,
                                timestamp=datetime.combine(
                                    test_date, 
                                    datetime.min.time().replace(hour=hour)
                                )
                            )
                            test_data.append(result)
        
        # バルク作成
        Result.objects.bulk_create(test_data, batch_size=1000)
        logger.info(f"テスト用実績データ {len(test_data)} 件を作成しました")
    
    def test_migration_performance(self):
        """マイグレーションのパフォーマンステスト"""
        # 実績データ数を確認
        result_count = Result.objects.filter(line=self.test_line.name).count()
        self.assertGreater(result_count, 0, "テスト用実績データが作成されていません")
        
        # 既存の集計データをクリア
        WeeklyResultAggregation.objects.filter(line=self.test_line.name).delete()
        
        # マイグレーション実行時間を測定
        start_time = time.time()
        
        # マイグレーション処理をシミュレート
        self.simulate_migration_process()
        
        migration_duration = time.time() - start_time
        
        # パフォーマンス要件をチェック
        max_allowed_time = 60  # 60秒以内
        self.assertLess(
            migration_duration, 
            max_allowed_time,
            f"マイグレーション時間が制限を超過: {migration_duration:.2f}秒 > {max_allowed_time}秒"
        )
        
        # 集計データが正しく作成されたかチェック
        aggregation_count = WeeklyResultAggregation.objects.filter(
            line=self.test_line.name
        ).count()
        self.assertGreater(aggregation_count, 0, "集計データが作成されていません")
        
        logger.info(f"マイグレーションパフォーマンステスト完了: {migration_duration:.2f}秒, {aggregation_count}件作成")
    
    def simulate_migration_process(self):
        """マイグレーション処理をシミュレート"""
        from django.db.models import Sum, Count
        
        # 実際のマイグレーション処理と同じロジック
        aggregated_data = list(Result.objects.filter(
            line=self.test_line.name
        ).values(
            'timestamp__date', 'machine', 'part', 'judgment'
        ).annotate(
            total_quantity=Sum('quantity'),
            result_count=Count('id')
        ))
        
        # バッチ処理で集計データを作成
        batch_size = 500
        aggregations_to_create = []
        
        for data in aggregated_data:
            aggregation = WeeklyResultAggregation(
                date=data['timestamp__date'],
                line=self.test_line.name,
                machine=data['machine'] or '',
                part=data['part'] or '',
                judgment=data['judgment'],
                total_quantity=data['total_quantity'] or 0,
                result_count=data['result_count'] or 0
            )
            aggregations_to_create.append(aggregation)
            
            # バッチサイズに達したら保存
            if len(aggregations_to_create) >= batch_size:
                WeeklyResultAggregation.objects.bulk_create(
                    aggregations_to_create,
                    ignore_conflicts=True
                )
                aggregations_to_create = []
        
        # 残りのデータを保存
        if aggregations_to_create:
            WeeklyResultAggregation.objects.bulk_create(
                aggregations_to_create,
                ignore_conflicts=True
            )
    
    def test_memory_usage(self):
        """メモリ使用量テスト"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # マイグレーション処理を実行
        self.simulate_migration_process()
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = memory_after - memory_before
        
        # メモリ使用量の制限をチェック
        max_memory_mb = 100  # 100MB以内
        self.assertLess(
            memory_used,
            max_memory_mb,
            f"メモリ使用量が制限を超過: {memory_used:.1f}MB > {max_memory_mb}MB"
        )
        
        logger.info(f"メモリ使用量テスト完了: {memory_used:.1f}MB使用")
    
    def test_data_consistency(self):
        """データ整合性テスト"""
        # マイグレーション処理を実行
        self.simulate_migration_process()
        
        # 元データと集計データの整合性をチェック
        original_total = Result.objects.filter(
            line=self.test_line.name
        ).aggregate(
            total_quantity=Sum('quantity'),
            total_count=Count('id')
        )
        
        aggregated_total = WeeklyResultAggregation.objects.filter(
            line=self.test_line.name
        ).aggregate(
            total_quantity=Sum('total_quantity'),
            total_count=Sum('result_count')
        )
        
        # 数量の整合性チェック
        self.assertEqual(
            original_total['total_quantity'],
            aggregated_total['total_quantity'],
            "集計数量が元データと一致しません"
        )
        
        # 件数の整合性チェック
        self.assertEqual(
            original_total['total_count'],
            aggregated_total['total_count'],
            "集計件数が元データと一致しません"
        )
        
        logger.info("データ整合性テスト完了: 元データと集計データが一致")
    
    def test_chunk_processing(self):
        """チャンク処理テスト"""
        # 大量データでのチャンク処理をテスト
        chunk_sizes = [100, 500, 1000]
        
        for chunk_size in chunk_sizes:
            with self.subTest(chunk_size=chunk_size):
                # 既存の集計データをクリア
                WeeklyResultAggregation.objects.filter(line=self.test_line.name).delete()
                
                start_time = time.time()
                
                # チャンクサイズを指定してマイグレーション処理
                self.simulate_chunk_migration(chunk_size)
                
                duration = time.time() - start_time
                
                # 結果を検証
                aggregation_count = WeeklyResultAggregation.objects.filter(
                    line=self.test_line.name
                ).count()
                
                self.assertGreater(aggregation_count, 0, f"チャンクサイズ{chunk_size}で集計データが作成されていません")
                
                logger.info(f"チャンクサイズ{chunk_size}: {duration:.2f}秒, {aggregation_count}件作成")
    
    def simulate_chunk_migration(self, chunk_size):
        """チャンク処理をシミュレート"""
        from django.db.models import Sum, Count
        
        # 日付範囲を取得
        date_range = Result.objects.filter(
            line=self.test_line.name
        ).values_list('timestamp__date', flat=True).distinct().order_by('timestamp__date')
        
        date_list = list(date_range)
        
        # 日付をチャンクに分割
        date_chunks = [
            date_list[i:i + chunk_size] 
            for i in range(0, len(date_list), chunk_size)
        ]
        
        # チャンク別処理
        for date_chunk in date_chunks:
            with transaction.atomic():
                aggregated_data = list(Result.objects.filter(
                    line=self.test_line.name,
                    timestamp__date__in=date_chunk
                ).values(
                    'timestamp__date', 'machine', 'part', 'judgment'
                ).annotate(
                    total_quantity=Sum('quantity'),
                    result_count=Count('id')
                ))
                
                # バルク作成
                aggregations_to_create = []
                for data in aggregated_data:
                    aggregation = WeeklyResultAggregation(
                        date=data['timestamp__date'],
                        line=self.test_line.name,
                        machine=data['machine'] or '',
                        part=data['part'] or '',
                        judgment=data['judgment'],
                        total_quantity=data['total_quantity'] or 0,
                        result_count=data['result_count'] or 0
                    )
                    aggregations_to_create.append(aggregation)
                
                if aggregations_to_create:
                    WeeklyResultAggregation.objects.bulk_create(
                        aggregations_to_create,
                        ignore_conflicts=True,
                        batch_size=500
                    )


class MigrationRollbackTest(TransactionTestCase):
    """
    マイグレーションロールバックテスト
    """
    databases = ['default']
    
    def setUp(self):
        """テストデータの準備"""
        # テスト用集計データを作成
        self.create_test_aggregation_data()
    
    def create_test_aggregation_data(self):
        """テスト用集計データを作成"""
        test_data = []
        base_date = date.today() - timedelta(days=10)
        
        for day_offset in range(10):
            test_date = base_date + timedelta(days=day_offset)
            
            aggregation = WeeklyResultAggregation(
                date=test_date,
                line='TEST_LINE',
                machine='TEST_MACHINE',
                part='TEST_PART',
                judgment='OK',
                total_quantity=100,
                result_count=10
            )
            test_data.append(aggregation)
        
        WeeklyResultAggregation.objects.bulk_create(test_data)
        logger.info(f"テスト用集計データ {len(test_data)} 件を作成しました")
    
    def test_rollback_performance(self):
        """ロールバックのパフォーマンステスト"""
        # 集計データ数を確認
        initial_count = WeeklyResultAggregation.objects.count()
        self.assertGreater(initial_count, 0, "テスト用集計データが作成されていません")
        
        # ロールバック実行時間を測定
        start_time = time.time()
        
        # ロールバック処理をシミュレート
        self.simulate_rollback_process()
        
        rollback_duration = time.time() - start_time
        
        # パフォーマンス要件をチェック
        max_allowed_time = 30  # 30秒以内
        self.assertLess(
            rollback_duration,
            max_allowed_time,
            f"ロールバック時間が制限を超過: {rollback_duration:.2f}秒 > {max_allowed_time}秒"
        )
        
        # データが削除されたかチェック
        final_count = WeeklyResultAggregation.objects.count()
        self.assertEqual(final_count, 0, "ロールバック後にデータが残っています")
        
        logger.info(f"ロールバックパフォーマンステスト完了: {rollback_duration:.2f}秒, {initial_count}件削除")
    
    def simulate_rollback_process(self):
        """ロールバック処理をシミュレート"""
        # チャンク削除
        chunk_size = 1000
        
        while True:
            ids_to_delete = list(
                WeeklyResultAggregation.objects.values_list('id', flat=True)[:chunk_size]
            )
            
            if not ids_to_delete:
                break
            
            with transaction.atomic():
                WeeklyResultAggregation.objects.filter(
                    id__in=ids_to_delete
                ).delete()