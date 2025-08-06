#!/usr/bin/env python
import os
import django

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from production.utils import get_dashboard_data

def test_dashboard_data():
    print("=== ダッシュボードデータテスト ===")
    
    # ライン1、2025-08-02のデータを取得
    dashboard_data = get_dashboard_data(1, '2025-08-02')
    
    print(f"総計画数量: {dashboard_data['total_planned']}")
    print(f"総実績数量: {dashboard_data['total_actual']}")
    print(f"達成率: {dashboard_data['achievement_rate']:.1f}%")
    print(f"残数: {dashboard_data['remaining']}")
    
    print(f"\n=== 機種別データ ===")
    for part in dashboard_data['parts']:
        print(f"機種: {part['name']}")
        print(f"  計画: {part['planned']}, 実績: {part['actual']}, 達成率: {part['achievement_rate']:.1f}%")
    
    print(f"\n=== 時間別データ ===")
    hourly_data = dashboard_data['hourly']
    if hourly_data:
        for hour_data in hourly_data[:5]:  # 最初の5時間を表示
            print(f"時間: {hour_data.get('hour', 'N/A')}, 計画: {hour_data.get('planned', 0)}, 実績: {hour_data.get('actual', 0)}")

if __name__ == '__main__':
    test_dashboard_data()