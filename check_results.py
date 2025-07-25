import os
import django
from datetime import datetime, timedelta
from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from collections import defaultdict
import pytz

# Django設定を読み込む
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from production.models import Result, Plan

# JSTタイムゾーンを取得
jst = pytz.timezone('Asia/Tokyo')

# 2025-06-01の実績を確認
target_date = datetime(2025, 6, 1).date()

# ライン79の実績を確認
line_no = 79

# 計画データを取得
plans = Plan.objects.filter(
    date=target_date,
    line_id=line_no
).order_by('sequence')

print(f"\n=== ライン{line_no}の計画 ({target_date}) ===")
total_planned = 0
for plan in plans:
    print(f"機種: {plan.part.name}, 計画数: {plan.planned_quantity}, 順序: {plan.sequence}")
    total_planned += plan.planned_quantity
print(f"計画合計: {total_planned}個")

# 実績データを取得
results = Result.objects.filter(
    timestamp__date=target_date,
    plan__line_id=line_no
).order_by('timestamp')

# 時間帯ごとの集計
print("\n=== 時間帯ごとの実績 ===\n")
hourly_results = defaultdict(lambda: defaultdict(int))
for result in results:
    # タイムゾーンを考慮した時刻を取得
    local_time = result.timestamp.astimezone(jst)
    hour = local_time.strftime('%H:00')
    hourly_results[hour][result.part.name] += result.quantity

# 時間帯ごとの出力
for hour in sorted(hourly_results.keys()):
    print(f"時間帯: {hour}")
    hour_total = 0
    for part_name, quantity in hourly_results[hour].items():
        print(f"  {part_name}: {quantity}個")
        hour_total += quantity
    print(f"  合計: {hour_total}個\n")

# 機種ごとの集計
print("=== 機種ごとの実績合計 ===")
for plan in plans:
    plan_results = results.filter(plan=plan)
    ok_count = plan_results.filter(judgment='OK').count()
    ng_count = plan_results.filter(judgment='NG').count()
    total_count = ok_count + ng_count
    print(f"機種: {plan.part.name}")
    print(f"  総生産数: {total_count}個 (OK: {ok_count}個, NG: {ng_count}個)")

# 合計
total_ok = results.filter(judgment='OK').count()
total_ng = results.filter(judgment='NG').count()
total_results = total_ok + total_ng

print("\n合計:")
print(f"  計画数: {total_planned}個")
print(f"  実績数: {total_results}個 (OK: {total_ok}個, NG: {total_ng}個)")

# 時間範囲
if results.exists():
    start_time = results.order_by('timestamp').first().timestamp.astimezone(jst)
    end_time = results.order_by('timestamp').last().timestamp.astimezone(jst)
    print("\n時間:")
    print(f"  開始時刻: {start_time.strftime('%H:%M:%S')}")
    print(f"  最終時刻: {end_time.strftime('%H:%M:%S')}")

    # 機種ごとの時間範囲
    print("\n=== 機種ごとの時間範囲 ===")
    for plan in plans:
        plan_results = results.filter(plan=plan)
        if plan_results.exists():
            start = plan_results.order_by('timestamp').first().timestamp.astimezone(jst)
            end = plan_results.order_by('timestamp').last().timestamp.astimezone(jst)
            duration = (end - start).total_seconds() / 60
            print(f"機種: {plan.part.name}")
            print(f"  開始: {start.strftime('%H:%M:%S')}")
            print(f"  終了: {end.strftime('%H:%M:%S')}")
            print(f"  所要時間: {duration:.1f}分") 