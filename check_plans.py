#!/usr/bin/env python
import os
import django
from datetime import date

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from production.models import Plan, Line

def check_plans():
    target_date = date(2025, 8, 2)
    
    print("=== 2025-08-02の全計画データ ===")
    plans = Plan.objects.filter(date=target_date).order_by('line__name', 'sequence')
    
    if not plans.exists():
        print("2025-08-02の計画データが存在しません！")
        return
    
    for plan in plans:
        print(f'ライン: {plan.line.name} (ID:{plan.line.id}), 機種: {plan.part.name}, 数量: {plan.planned_quantity}')
    
    print(f"\n=== ライン別集計 ===")
    from django.db.models import Count, Sum
    line_summary = Plan.objects.filter(date=target_date).values('line__name', 'line__id').annotate(
        count=Count('id'),
        total_qty=Sum('planned_quantity')
    ).order_by('line__name')
    
    for summary in line_summary:
        print(f"ライン: {summary['line__name']} (ID:{summary['line__id']}) - 計画数: {summary['count']}, 総数量: {summary['total_qty']}")
    
    print(f"\n=== ライン1 (KAHA01) の詳細確認 ===")
    line1_plans = Plan.objects.filter(date=target_date, line_id=1)
    if line1_plans.exists():
        for plan in line1_plans:
            print(f'時間: {plan.start_time}-{plan.end_time}, 機種: {plan.part.name}, 数量: {plan.planned_quantity}')
    else:
        print("ライン1 (KAHA01) の計画データがありません！")
        
        # 他の日にデータがあるか確認
        from datetime import timedelta
        for delta in range(-10, 11):
            check_date = target_date + timedelta(days=delta)
            if Plan.objects.filter(date=check_date, line_id=1).exists():
                count = Plan.objects.filter(date=check_date, line_id=1).count()
                print(f"  {check_date} には {count} 件の計画があります")

if __name__ == '__main__':
    check_plans()