#!/usr/bin/env python
import os
import sys
import django

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
sys.path.append('/app')
django.setup()

from production.models import Machine, Plan, Result
from production.views import DashboardDataAPIView
from django.test import RequestFactory
from django.contrib.auth.models import User
from datetime import date

def test_dashboard_data():
    print("=== Dashboard Data Test ===")
    
    # Machine ID 1の確認
    try:
        machine = Machine.objects.get(id=1)
        print(f"Machine 1: {machine.name}")
    except Machine.DoesNotExist:
        print("Machine 1 not found")
        return
    
    # 2025-08-15のPlanデータ確認
    plans = Plan.objects.filter(machine_id=1, date=date(2025, 8, 15))
    print(f"Plans for Machine 1 on 2025-08-15: {plans.count()}")
    
    # Oracleからの実績データ確認
    try:
        results = Result.objects.using('oracle').filter(machine='KAHA01-M01')[:5]
        print(f"Results from Oracle for KAHA01-M01: {results.count()}")
        for result in results:
            print(f"  - {result.timestamp}: {result.judgment}")
    except Exception as e:
        print(f"Oracle query error: {e}")
    
    # APIビューのテスト
    factory = RequestFactory()
    request = factory.get('/production/api/dashboard-data/1/2025-08-15/')
    
    # スーパーユーザーでログイン
    user = User.objects.filter(is_superuser=True).first()
    request.user = user
    
    view = DashboardDataAPIView()
    try:
        response = view.get(request, line_id=1, date='2025-08-15')
        print(f"API Response Status: {response.status_code}")
        if hasattr(response, 'data'):
            print(f"API Response Data: {response.data}")
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == '__main__':
    test_dashboard_data()