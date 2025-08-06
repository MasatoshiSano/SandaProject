#!/usr/bin/env python
import os
import django
from datetime import date, datetime, time

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from production.models import Result

def test_result_counts():
    target_date = date(2025, 8, 2)
    
    print("=== Result モデル詳細確認 ===")
    
    # 全データ
    all_count = Result.objects.filter(timestamp__date=target_date, line='KAHA01').count()
    print(f'KAHA01の全データ: {all_count}件')
    
    # OK判定のみ
    ok_count = Result.objects.filter(timestamp__date=target_date, line='KAHA01', judgment='OK').count()
    print(f'KAHA01のOK判定: {ok_count}件')
    
    # NG判定のみ
    ng_count = Result.objects.filter(timestamp__date=target_date, line='KAHA01', judgment='NG').count()
    print(f'KAHA01のNG判定: {ng_count}件')
    
    # 時間範囲での確認（get_dashboard_dataと同じ条件）
    start_dt = datetime.combine(target_date, time.min)
    end_dt = datetime.combine(target_date, time.max)
    
    range_all = Result.objects.filter(
        line='KAHA01',
        timestamp__range=(start_dt, end_dt)
    ).count()
    print(f'時間範囲指定（全判定）: {range_all}件')
    
    range_ok = Result.objects.filter(
        line='KAHA01',
        timestamp__range=(start_dt, end_dt),
        judgment='OK'
    ).count()
    print(f'時間範囲指定（OK判定）: {range_ok}件')
    
    # サンプルデータ確認
    print(f'\n=== サンプルデータ ===')
    samples = Result.objects.filter(timestamp__date=target_date, line='KAHA01')[:10]
    for sample in samples:
        print(f'{sample.timestamp} - {sample.judgment} - {sample.part} - 数量: {getattr(sample, "quantity", "N/A")}')

if __name__ == '__main__':
    test_result_counts()