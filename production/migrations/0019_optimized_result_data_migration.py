# Generated for weekly analysis performance improvement - Optimized migration with performance enhancements

from django.db import migrations, transaction, connection
from django.db.models import Sum, Count
from datetime import datetime, date, timedelta
import logging
import time
import gc

logger = logging.getLogger(__name__)


def optimized_migrate_result_data(apps, schema_editor):
    """
    既存のResultデータを集計テーブルに移行（最適化版）
    - チャンク処理でメモリ効率化
    - 接続プール最適化
    - 進捗監視とログ
    - パフォーマンス測定
    """
    # モデルを取得
    Result = apps.get_model('production', 'Result')
    WeeklyResultAggregation = apps.get_model('production', 'WeeklyResultAggregation')
    Line = apps.get_model('production', 'Line')
    
    start_time = time.time()
    logger.info("最適化された既存Resultデータ移行を開始します")
    
    # データベース接続の最適化（データベース種別に応じて）
    db_vendor = connection.vendor
    logger.info(f"データベース種別: {db_vendor}")
    
    try:
        with connection.cursor() as cursor:
            if db_vendor == 'oracle':
                # Oracle固有の最適化設定
                cursor.execute("ALTER SESSION SET OPTIMIZER_MODE = ALL_ROWS")
                cursor.execute("ALTER SESSION SET SORT_AREA_SIZE = 10485760")  # 10MB
                logger.info("Oracle データベース接続を最適化しました")
            elif db_vendor == 'postgresql':
                # PostgreSQL固有の最適化設定
                cursor.execute("SET work_mem = '16MB'")
                cursor.execute("SET maintenance_work_mem = '64MB'")
                logger.info("PostgreSQL データベース接続を最適化しました")
            else:
                logger.info(f"データベース {db_vendor} の最適化設定はスキップします")
    except Exception as e:
        logger.warning(f"データベース最適化設定でエラー: {e}")
    
    # 既存の集計データを確認
    existing_count = WeeklyResultAggregation.objects.count()
    if existing_count > 0:
        logger.info(f"既存の集計データ {existing_count} 件が存在します（追加処理）")
    else:
        logger.info("新規集計データ作成")
    
    # 有効なラインを取得
    active_lines = Line.objects.filter(is_active=True).order_by('name')
    if not active_lines.exists():
        logger.warning("有効なラインが見つかりません。移行をスキップします。")
        return
    
    # 実績データの統計を取得
    total_results = Result.objects.count()
    if total_results == 0:
        logger.info("実績データが見つかりません。移行をスキップします。")
        return
    
    logger.info(f"移行対象: {active_lines.count()}ライン, 実績データ{total_results}件")
    
    # 移行統計
    migration_stats = {
        'total_lines': active_lines.count(),
        'processed_lines': 0,
        'total_aggregations': 0,
        'total_processing_time': 0,
        'errors': 0,
        'memory_usage_mb': 0
    }
    
    # ライン別に処理（チャンク処理）
    for line_index, line in enumerate(active_lines, 1):
        line_start_time = time.time()
        logger.info(f"ライン '{line.name}' の処理を開始 ({line_index}/{active_lines.count()})")
        line_aggregations = 0
        
        try:
            # メモリ使用量監視（簡易版）
            import resource
            memory_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB (Linux)
            
            # 該当ラインの実績データ数を確認
            line_result_count = Result.objects.filter(line=line.name).count()
            logger.info(f"ライン '{line.name}': {line_result_count}件の実績データを処理")
            
            if line_result_count == 0:
                logger.info(f"ライン '{line.name}' に実績データがありません")
                migration_stats['processed_lines'] += 1
                continue
            
            # チャンクサイズを動的に調整（データ量に応じて）
            if line_result_count > 10000:
                chunk_size = 1000
            elif line_result_count > 1000:
                chunk_size = 500
            else:
                chunk_size = 100
            
            logger.info(f"ライン '{line.name}': チャンクサイズ {chunk_size} で処理")
            
            # 日付範囲を取得してチャンク処理
            date_range = Result.objects.filter(
                line=line.name
            ).values_list('timestamp__date', flat=True).distinct().order_by('timestamp__date')
            
            date_list = list(date_range)
            total_dates = len(date_list)
            
            # 日付をチャンクに分割
            date_chunks = [
                date_list[i:i + chunk_size] 
                for i in range(0, len(date_list), chunk_size)
            ]
            
            logger.info(f"ライン '{line.name}': {total_dates}日分を{len(date_chunks)}チャンクで処理")
            
            # チャンク別処理
            for chunk_index, date_chunk in enumerate(date_chunks, 1):
                chunk_start_time = time.time()
                
                try:
                    # チャンク内の日付範囲で集計
                    with transaction.atomic():
                        aggregated_data = list(Result.objects.filter(
                            line=line.name,
                            timestamp__date__in=date_chunk
                        ).values(
                            'timestamp__date', 'machine', 'part', 'judgment'
                        ).annotate(
                            total_quantity=Sum('quantity'),
                            result_count=Count('id')
                        ))
                        
                        # バルク作成用のデータを準備
                        aggregations_to_create = []
                        for data in aggregated_data:
                            aggregation = WeeklyResultAggregation(
                                date=data['timestamp__date'],
                                line=line.name,
                                machine=data['machine'] or '',
                                part=data['part'] or '',
                                judgment=data['judgment'],
                                total_quantity=data['total_quantity'] or 0,
                                result_count=data['result_count'] or 0
                            )
                            aggregations_to_create.append(aggregation)
                        
                        # バルク作成（重複無視）
                        if aggregations_to_create:
                            created_count = len(WeeklyResultAggregation.objects.bulk_create(
                                aggregations_to_create,
                                ignore_conflicts=True,
                                batch_size=500
                            ))
                            line_aggregations += created_count
                            migration_stats['total_aggregations'] += created_count
                
                except Exception as e:
                    logger.error(f"チャンク {chunk_index} 処理エラー: {e}")
                    migration_stats['errors'] += 1
                    continue
                
                # チャンク処理時間とメモリ使用量をログ
                chunk_duration = time.time() - chunk_start_time
                memory_current = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB
                
                logger.info(
                    f"ライン '{line.name}' チャンク {chunk_index}/{len(date_chunks)} 完了: "
                    f"{len(aggregated_data)}件作成, {chunk_duration:.2f}秒, "
                    f"メモリ使用量: {memory_current:.1f}MB"
                )
                
                # メモリクリーンアップ
                if chunk_index % 5 == 0:  # 5チャンクごとにガベージコレクション
                    gc.collect()
            
            # ライン処理完了統計
            line_duration = time.time() - line_start_time
            memory_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB
            memory_used = memory_after - memory_before
            
            migration_stats['processed_lines'] += 1
            migration_stats['total_processing_time'] += line_duration
            migration_stats['memory_usage_mb'] = max(migration_stats['memory_usage_mb'], memory_after)
            
            logger.info(
                f"ライン '{line.name}' 完了: {line_aggregations}件作成, "
                f"処理時間{line_duration:.2f}秒, メモリ使用量+{memory_used:.1f}MB "
                f"({migration_stats['processed_lines']}/{migration_stats['total_lines']})"
            )
            
        except Exception as e:
            logger.error(f"ライン '{line.name}' の処理で致命的エラー: {e}")
            migration_stats['errors'] += 1
            migration_stats['processed_lines'] += 1
            continue
    
    # 移行完了統計
    total_duration = time.time() - start_time
    
    logger.info("=== 最適化移行完了統計 ===")
    logger.info(f"処理ライン数: {migration_stats['processed_lines']}/{migration_stats['total_lines']}")
    logger.info(f"作成集計レコード数: {migration_stats['total_aggregations']}")
    logger.info(f"総処理時間: {total_duration:.2f}秒")
    logger.info(f"平均ライン処理時間: {migration_stats['total_processing_time']/max(migration_stats['processed_lines'], 1):.2f}秒")
    logger.info(f"最大メモリ使用量: {migration_stats['memory_usage_mb']:.1f}MB")
    logger.info(f"エラー数: {migration_stats['errors']}")
    
    if migration_stats['total_aggregations'] > 0:
        avg_time_per_record = total_duration / migration_stats['total_aggregations']
        logger.info(f"平均処理時間: {avg_time_per_record:.4f}秒/レコード")
    
    # 最終検証
    final_count = WeeklyResultAggregation.objects.count()
    logger.info(f"最終集計レコード数: {final_count}")
    
    # パフォーマンステスト
    logger.info("=== パフォーマンステスト ===")
    test_start = time.time()
    sample_aggregations = WeeklyResultAggregation.objects.select_related().all()[:100]
    test_duration = time.time() - test_start
    logger.info(f"100件取得テスト: {test_duration:.4f}秒")


def reverse_optimized_migration(apps, schema_editor):
    """
    最適化移行のロールバック（チャンク削除）
    """
    WeeklyResultAggregation = apps.get_model('production', 'WeeklyResultAggregation')
    
    logger.info("最適化移行のロールバックを開始します")
    start_time = time.time()
    
    # 集計データの統計
    total_count = WeeklyResultAggregation.objects.count()
    logger.info(f"削除対象: {total_count}件の集計レコード")
    
    if total_count == 0:
        logger.info("削除対象のデータがありません")
        return
    
    # チャンク削除（大量データ対応）
    chunk_size = 5000
    deleted_total = 0
    
    while True:
        # チャンクサイズ分のIDを取得
        ids_to_delete = list(
            WeeklyResultAggregation.objects.values_list('id', flat=True)[:chunk_size]
        )
        
        if not ids_to_delete:
            break
        
        # チャンク削除
        with transaction.atomic():
            deleted_count = WeeklyResultAggregation.objects.filter(
                id__in=ids_to_delete
            ).delete()[0]
        
        deleted_total += deleted_count
        logger.info(f"削除進捗: {deleted_total}/{total_count}")
        
        if deleted_count < chunk_size:
            break
    
    duration = time.time() - start_time
    logger.info(f"最適化ロールバック完了: {deleted_total}件削除, 処理時間{duration:.2f}秒")


class Migration(migrations.Migration):
    
    dependencies = [
        ('production', '0018_migrate_existing_result_data'),
    ]
    
    operations = [
        migrations.RunPython(
            optimized_migrate_result_data,
            reverse_optimized_migration,
            hints={'target_db': 'default'}
        ),
    ]