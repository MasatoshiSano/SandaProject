#!/usr/bin/env python
import os
import sys
import django

# Djangoプロジェクトの設定を読み込み
sys.path.append('/home/sano/SandaDev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.models import Result, Line, Plan
from django.db.models import Min, Max, Count

def check_data_dates():
    """データの日付範囲を確認"""
    try:
        print("=== Line 3のデータ確認 ===")
        
        line3 = Line.objects.get(id=3)
        print(f"Line 3: {line3.name}")
        
        # Result データの日付範囲
        result_dates = Result.objects.filter(line=line3.name).aggregate(
            min_date=Min('timestamp'),
            max_date=Max('timestamp'),
            count=Count('id')
        )
        print(f"Result データ: {result_dates['count']}件")
        print(f"  最初: {result_dates['min_date']}")
        print(f"  最後: {result_dates['max_date']}")
        
        # Plan データの日付範囲
        plan_dates = Plan.objects.filter(line=line3).aggregate(
            min_date=Min('date'),
            max_date=Max('date'),
            count=Count('id')
        )
        print(f"Plan データ: {plan_dates['count']}件")
        print(f"  最初: {plan_dates['min_date']}")
        print(f"  最後: {plan_dates['max_date']}")
        
        # 特定日のデータを確認
        from production.utils import get_dashboard_data
        
        if result_dates['min_date']:
            test_date = result_dates['min_date'].strftime('%Y-%m-%d')
            print(f"\n=== {test_date}のダッシュボードデータテスト ===")
            dashboard_data = get_dashboard_data(3, test_date)
            print(f"計画数: {len(dashboard_data.get('plans', []))}")
            print(f"実績数: {len(dashboard_data.get('results', []))}")
            
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_data_dates()