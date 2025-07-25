import os
import django
from datetime import datetime
from django.db import models
from django.utils import timezone

# Django設定を読み込む
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from production.models import Result, Plan

# 2025-06-01の実績を確認
target_date = datetime(2025, 6, 1).date()
line_no = 79

# 実績データを取得（全件表示）
results = Result.objects.filter(
    timestamp__date=target_date,
    plan__line_id=line_no
).order_by('timestamp')

print(f"\n=== 実績データの詳細 ===")
for result in results:
    print(f"時刻: {result.timestamp.strftime('%H:%M:%S')}, "
          f"機種: {result.part.name}, "
          f"判定: {result.judgment}, "
          f"シリアル: {result.serial_number}")

# 機種ごとの集計
print(f"\n=== 機種ごとの集計 ===")
for plan in Plan.objects.filter(date=target_date, line_id=line_no).order_by('sequence'):
    results = Result.objects.filter(
        timestamp__date=target_date,
        plan=plan
    )
    ok_count = results.filter(judgment='OK').count()
    ng_count = results.filter(judgment='NG').count()
    
    print(f"\n機種: {plan.part.name}")
    print(f"  計画数: {plan.planned_quantity}")
    print(f"  実績数: {ok_count + ng_count}個 (OK: {ok_count}個, NG: {ng_count}個)")
    
    if results.exists():
        first = results.order_by('timestamp').first()
        last = results.order_by('timestamp').last()
        print(f"  開始時刻: {first.timestamp.strftime('%H:%M:%S')}")
        print(f"  終了時刻: {last.timestamp.strftime('%H:%M:%S')}") 