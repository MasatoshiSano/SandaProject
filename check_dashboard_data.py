#!/usr/bin/env python
import os
import django
from datetime import date, datetime

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections
from production.models import Result, Line

def check_data():
    print("=== データベース直接確認 ===")
    oracle_conn = connections['oracle']
    
    # 2025-08-02のデータ確認
    with oracle_conn.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*), MIN(timestamp), MAX(timestamp) 
            FROM production_result 
            WHERE timestamp >= TO_DATE('2025-08-02', 'YYYY-MM-DD')
            AND timestamp < TO_DATE('2025-08-03', 'YYYY-MM-DD')
        """)
        result = cursor.fetchone()
        print(f'2025-08-02の件数: {result[0]}')
        if result[1]:
            print(f'最小時刻: {result[1]}, 最大時刻: {result[2]}')
        
        # ライン・機種別の詳細
        cursor.execute("""
            SELECT line, machine, part, judgment, COUNT(*) 
            FROM production_result 
            WHERE timestamp >= TO_DATE('2025-08-02', 'YYYY-MM-DD')
            AND timestamp < TO_DATE('2025-08-03', 'YYYY-MM-DD')
            GROUP BY line, machine, part, judgment
            ORDER BY line, machine, part, judgment
        """)
        results = cursor.fetchall()
        print('\n=== 2025-08-02のデータ詳細 ===')
        for row in results:
            print(f'ライン: {row[0]}, 設備: {row[1]}, 機種: {row[2]}, 判定: {row[3]}, 件数: {row[4]}')

    print('\n=== Djangoモデル経由の確認 ===')
    try:
        target_date = date(2025, 8, 2)
        count = Result.objects.filter(timestamp__date=target_date).count()
        print(f'Djangoモデル経由の件数: {count}')
        
        if count > 0:
            sample = Result.objects.filter(timestamp__date=target_date).first()
            print(f'サンプルデータ: {sample.line}, {sample.machine}, {sample.part}, {sample.judgment}')
            print(f'タイムスタンプ: {sample.timestamp}')
        
        # ライン1（KAHA01）の確認
        line1_count = Result.objects.filter(timestamp__date=target_date, line='KAHA01').count()
        print(f'ライン1（KAHA01）の件数: {line1_count}')
        
    except Exception as e:
        print(f'Djangoモデルエラー: {e}')

    print('\n=== ライン情報確認 ===')
    try:
        lines = Line.objects.all()
        for line in lines:
            print(f'ライン {line.id}: {line.name}')
    except Exception as e:
        print(f'ライン確認エラー: {e}')

if __name__ == '__main__':
    check_data()