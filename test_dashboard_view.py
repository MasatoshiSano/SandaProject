#!/usr/bin/env python
import os
import sys
import django

# Djangoプロジェクトの設定を読み込み
sys.path.append('/home/sano/SandaDev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.utils import get_dashboard_data

def test_dashboard_data():
    """ダッシュボードデータ取得のテスト"""
    try:
        print("=== ダッシュボードデータテスト ===")
        
        # Line 3, 2025-08-05のダッシュボードデータを取得
        dashboard_data = get_dashboard_data(3, '2025-08-05')
        
        print(f"ダッシュボードデータ取得成功")
        print(f"計画数: {len(dashboard_data.get('plans', []))}")
        print(f"実績数: {len(dashboard_data.get('results', []))}")
        print(f"機種データ: {len(dashboard_data.get('part_data', {}))}")
        
        # 機種データの詳細表示
        for part_name, data in dashboard_data.get('part_data', {}).items():
            print(f"  {part_name}: 計画={data.get('planned', 0)}, 実績={data.get('actual', 0)}")
        
    except Exception as e:
        print(f"ダッシュボードデータテストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dashboard_data()