# Generated for weekly analysis performance improvement - Safe data migration

from django.db import migrations, transaction
from django.db.models import Sum, Count
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


def migrate_existing_result_data(apps, schema_editor):
    """
    既存のResultデータを集計テーブルに移行（安全版）
    - 重複回避
    - 進捗監視
    - エラー回復
    """
    # モデルを取得
    Result = apps.get_model('production', 'Result')
    WeeklyResultAggregation = apps.get_model('production', 'WeeklyResultAggregation')
    Line = apps.get_model('production', 'Line')
    
    logger.info("安全な既存Resultデータ移行を開始します")
    
    # 既存の集計データを確実にクリア
    existing_count = WeeklyResultAggregation.objects.count()
    if existing_count > 0:
        logger.info(f"既存の集計データ {existing_count} 件をクリアします")
        WeeklyResultAggregation.objects.all().delete()
        logger.info("既存の集計データをクリアしました")
    else:
        logger.info("既存の集計データはありません")
    
    # 有効なラインを取得
    active_lines = Line.objects.filter(is_active=True)
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
        'errors': 0,
        'skipped_combinations': 0
    }
    
    # ライン別に処理
    for line in active_lines:
        logger.info(f"ライン '{line.name}' の処理を開始")
        line_aggregations = 0
        
        try:
            # 該当ラインの実績データを日付・機種・設備・判定別に直接集計
            logger.info(f"ライン '{line.name}' のデータを集計中...")
            
            aggregated_data = list(Result.objects.filter(
                line=line.name
            ).values(
                'timestamp__date', 'machine', 'part', 'judgment'
            ).annotate(
                total_quantity=Sum('quantity'),
                result_count=Count('id')
            ))
            
            logger.info(f"ライン '{line.name}': {len(aggregated_data)}件の集計組み合わせを処理")
            
            # バッチ処理で集計データを作成（重複チェックなし、高速処理）
            batch_size = 500
            aggregations_to_create = []
            
            for i, data in enumerate(aggregated_data):
                try:
                    # 集計レコードを準備
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
                    
                    # バッチサイズに達したら保存
                    if len(aggregations_to_create) >= batch_size:
                        try:
                            WeeklyResultAggregation.objects.bulk_create(
                                aggregations_to_create,
                                ignore_conflicts=True  # 重複を無視
                            )
                            line_aggregations += len(aggregations_to_create)
                            migration_stats['total_aggregations'] += len(aggregations_to_create)
                            logger.info(f"ライン '{line.name}': {line_aggregations}件保存完了 ({i+1}/{len(aggregated_data)})")
                        except Exception as e:
                            logger.error(f"バッチ保存エラー: {e}")
                            migration_stats['errors'] += 1
                        
                        aggregations_to_create = []
                
                except Exception as e:
                    logger.error(f"集計データ作成エラー: {e}")
                    migration_stats['errors'] += 1
                    continue
            
            # 残りのデータを保存
            if aggregations_to_create:
                try:
                    WeeklyResultAggregation.objects.bulk_create(
                        aggregations_to_create,
                        ignore_conflicts=True
                    )
                    line_aggregations += len(aggregations_to_create)
                    migration_stats['total_aggregations'] += len(aggregations_to_create)
                    logger.info(f"ライン '{line.name}': 最終バッチ {len(aggregations_to_create)}件保存完了")
                except Exception as e:
                    logger.error(f"最終バッチ保存エラー: {e}")
                    migration_stats['errors'] += 1
            
            migration_stats['processed_lines'] += 1
            logger.info(
                f"ライン '{line.name}' 完了: {line_aggregations}件作成 "
                f"({migration_stats['processed_lines']}/{migration_stats['total_lines']})"
            )
            
        except Exception as e:
            logger.error(f"ライン '{line.name}' の処理でエラー: {e}")
            migration_stats['errors'] += 1
            migration_stats['processed_lines'] += 1
            continue
    
    # 移行完了統計
    logger.info("=== 移行完了統計 ===")
    logger.info(f"処理ライン数: {migration_stats['processed_lines']}/{migration_stats['total_lines']}")
    logger.info(f"作成集計レコード数: {migration_stats['total_aggregations']}")
    logger.info(f"スキップした重複: {migration_stats['skipped_combinations']}")
    logger.info(f"エラー数: {migration_stats['errors']}")
    
    # 最終検証
    final_count = WeeklyResultAggregation.objects.count()
    logger.info(f"最終集計レコード数: {final_count}")


def reverse_migrate_result_data(apps, schema_editor):
    """
    移行のロールバック（集計データを削除）
    """
    WeeklyResultAggregation = apps.get_model('production', 'WeeklyResultAggregation')
    
    logger.info("集計データの移行をロールバックします")
    
    # 集計データを削除
    deleted_count = WeeklyResultAggregation.objects.all().delete()[0]
    
    logger.info(f"ロールバック完了: {deleted_count}件の集計レコードを削除")


class Migration(migrations.Migration):
    
    dependencies = [
        ('production', '0017_add_weekly_result_aggregation'),
    ]
    
    operations = [
        migrations.RunPython(
            migrate_existing_result_data,
            reverse_migrate_result_data,
            hints={'target_db': 'default'}
        ),
    ]