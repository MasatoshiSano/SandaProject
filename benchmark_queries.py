#!/usr/bin/env python3
"""
クエリパフォーマンス比較テスト
"""
import os
import sys
import django
import time
from datetime import datetime, date, timedelta

# Django設定
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from django.db.models import Count
from django.db import connection
from production.models import Result, Plan

def benchmark_orm_query(line_id, target_date, part_names, iterations=10):
    """Django ORM + GROUP BY のベンチマーク"""
    line_name = str(line_id).zfill(6)
    start_time = target_date.strftime('%Y%m%d') + '000000'
    end_time = (target_date + timedelta(days=1)).strftime('%Y%m%d') + '000000'
    
    times = []
    for i in range(iterations):
        start = time.time()
        
        results = Result.get_filtered_queryset().filter(
            line=line_name,
            part__in=part_names,
            judgment='1',
            timestamp__gte=start_time,
            timestamp__lt=end_time
        ).values('part').annotate(
            actual_count=Count('serial_number')
        )
        
        # 結果を辞書に変換（実際の使用パターン）
        result_dict = {result['part']: result['actual_count'] for result in results}
        
        end = time.time()
        times.append(end - start)
    
    return {
        'method': 'Django ORM + GROUP BY',
        'avg_time': sum(times) / len(times),
        'min_time': min(times),
        'max_time': max(times),
        'result_count': len(result_dict) if 'result_dict' in locals() else 0
    }

def benchmark_raw_sql(line_id, target_date, part_names, iterations=10):
    """生SQL のベンチマーク（Oracle接続使用）"""
    from django.db import connections
    
    line_name = str(line_id).zfill(6)
    start_time = target_date.strftime('%Y%m%d') + '000000'
    end_time = (target_date + timedelta(days=1)).strftime('%Y%m%d') + '000000'
    
    # Oracleデータベース接続を使用
    oracle_connection = connections['oracle']
    
    placeholders = ','.join([':part%d' % i for i in range(len(part_names))])
    sql = f"""
        SELECT partsname, COUNT(*) as actual_count
        FROM HF1REM01 
        WHERE STA_NO2 = :line_name
          AND partsname IN ({placeholders})
          AND OPEFIN_RESULT = '1'
          AND STA_NO1 = 'SAND'
          AND MK_DATE >= :start_time
          AND MK_DATE < :end_time
        GROUP BY partsname
    """
    
    # Oracle用のパラメータ辞書
    params = {'line_name': line_name, 'start_time': start_time, 'end_time': end_time}
    for i, part_name in enumerate(part_names):
        params[f'part{i}'] = part_name
    
    times = []
    for i in range(iterations):
        start = time.time()
        
        try:
            with oracle_connection.cursor() as cursor:
                cursor.execute(sql, params)
                results = cursor.fetchall()
            
            # 結果を辞書に変換（実際の使用パターン）
            result_dict = {row[0]: row[1] for row in results}
            
        except Exception as e:
            print(f"Oracle接続エラー: {e}")
            # フォールバック: ORMを使用
            results = Result.get_filtered_queryset().filter(
                line=line_name,
                part__in=part_names,
                judgment='1',
                timestamp__gte=start_time,
                timestamp__lt=end_time
            ).values('part').annotate(
                actual_count=Count('serial_number')
            )
            result_dict = {result['part']: result['actual_count'] for result in results}
        
        end = time.time()
        times.append(end - start)
    
    return {
        'method': '生SQL (Oracle)',
        'avg_time': sum(times) / len(times),
        'min_time': min(times),
        'max_time': max(times),
        'result_count': len(result_dict) if 'result_dict' in locals() else 0
    }

def main():
    """ベンチマーク実行"""
    print("=== クエリパフォーマンス比較テスト ===\n")
    
    # テスト条件
    line_id = 1
    target_date = date(2025, 8, 14)
    
    # 計画から機種名を取得
    plans = Plan.objects.filter(line_id=line_id, date=target_date)
    if not plans.exists():
        print("計画データが見つかりません")
        return
    
    part_names = [plan.part.name for plan in plans]
    print(f"テスト対象:")
    print(f"  ライン: {line_id}")
    print(f"  日付: {target_date}")
    print(f"  機種数: {len(part_names)}")
    print(f"  機種: {part_names}")
    print()
    
    # ベンチマーク実行
    iterations = 5
    print(f"各方式を{iterations}回実行してベンチマーク...\n")
    
    # Django ORM
    orm_result = benchmark_orm_query(line_id, target_date, part_names, iterations)
    
    # 生SQL
    raw_result = benchmark_raw_sql(line_id, target_date, part_names, iterations)
    
    # 結果表示
    print("=== 結果 ===")
    print(f"{'方式':<20} {'平均時間':<12} {'最小時間':<12} {'最大時間':<12} {'結果数':<8}")
    print("-" * 70)
    
    for result in [orm_result, raw_result]:
        print(f"{result['method']:<20} "
              f"{result['avg_time']*1000:>8.2f}ms "
              f"{result['min_time']*1000:>8.2f}ms "
              f"{result['max_time']*1000:>8.2f}ms "
              f"{result['result_count']:>6}")
    
    # パフォーマンス差の計算
    if orm_result['avg_time'] > 0:
        improvement = ((orm_result['avg_time'] - raw_result['avg_time']) / orm_result['avg_time']) * 100
        print(f"\n生SQLの改善率: {improvement:.1f}%")
        
        if improvement > 0:
            print(f"生SQLが {improvement:.1f}% 高速")
        else:
            print(f"ORMが {abs(improvement):.1f}% 高速")

if __name__ == '__main__':
    main()