#!/usr/bin/env python3
"""
ダッシュボードパフォーマンステスト（改善後）
"""
import os
import sys
import django
import time
from datetime import datetime, date

# Django設定
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.utils import get_dashboard_data, clear_dashboard_cache
from production.services.forecast_service import ForecastCalculationService

def test_dashboard_performance():
    """ダッシュボードデータ取得のパフォーマンステスト"""
    print("=== ダッシュボードパフォーマンステスト（改善後） ===\n")
    
    line_id = 1
    date_str = '2025-08-14'
    
    print(f"テスト条件:")
    print(f"  ライン: {line_id}")
    print(f"  日付: {date_str}")
    print()
    
    # キャッシュをクリアして初回実行をテスト
    print("0. キャッシュクリア...")
    clear_dashboard_cache(line_id, date_str)
    print("   ✅ キャッシュクリア完了")
    print()
    
    # ダッシュボードデータ取得テスト（初回 - キャッシュなし）
    print("1. ダッシュボードデータ取得テスト（初回 - キャッシュなし）...")
    start_time = time.time()
    
    try:
        dashboard_data = get_dashboard_data(line_id, date_str)
        end_time = time.time()
        
        print(f"   ✅ 成功: {(end_time - start_time)*1000:.2f}ms")
        print(f"   機種数: {len(dashboard_data.get('parts', []))}")
        print(f"   時間別データ: {len(dashboard_data.get('hourly', []))}時間")
        print(f"   計画総数: {dashboard_data.get('total_planned', 0)}")
        print(f"   実績総数: {dashboard_data.get('total_actual', 0)}")
        print(f"   達成率: {dashboard_data.get('achievement_rate', 0):.1f}%")
        
    except Exception as e:
        end_time = time.time()
        print(f"   ❌ エラー: {(end_time - start_time)*1000:.2f}ms - {e}")
    
    print()
    
    # ダッシュボードデータ取得テスト（2回目 - キャッシュあり）
    print("2. ダッシュボードデータ取得テスト（2回目 - キャッシュあり）...")
    start_time = time.time()
    
    try:
        dashboard_data = get_dashboard_data(line_id, date_str)
        end_time = time.time()
        
        print(f"   ✅ 成功: {(end_time - start_time)*1000:.2f}ms")
        print(f"   キャッシュ効果: {dashboard_data.get('last_updated', 'N/A')}")
        
    except Exception as e:
        end_time = time.time()
        print(f"   ❌ エラー: {(end_time - start_time)*1000:.2f}ms - {e}")
    
    print()
    
    # 終了予測計算テスト（最適化版）
    print("3. 終了予測計算テスト（最適化版・休憩段替え時間込み）...")
    start_time = time.time()
    
    try:
        from production.services.forecast_service import OptimizedForecastService
        optimized_service = OptimizedForecastService()
        forecast_time = optimized_service.get_forecast_time(line_id, date(2025, 8, 14))
        end_time = time.time()
        
        print(f"   ✅ 成功: {(end_time - start_time)*1000:.2f}ms")
        print(f"   予測時刻: {forecast_time}")
        
    except Exception as e:
        end_time = time.time()
        print(f"   ❌ エラー: {(end_time - start_time)*1000:.2f}ms - {e}")
    
    print()
    
    # 終了予測計算テスト（キャッシュ効果確認）
    print("4. 終了予測計算テスト（2回目・キャッシュ効果確認）...")
    start_time = time.time()
    
    try:
        from production.services.forecast_service import OptimizedForecastService
        optimized_service = OptimizedForecastService()
        forecast_time = optimized_service.get_forecast_time(line_id, date(2025, 8, 14))
        end_time = time.time()
        
        print(f"   ✅ 成功: {(end_time - start_time)*1000:.2f}ms")
        print(f"   予測時刻: {forecast_time}")
        print(f"   キャッシュ効果確認")
        
    except Exception as e:
        end_time = time.time()
        print(f"   ❌ エラー: {(end_time - start_time)*1000:.2f}ms - {e}")
    
    print()
    
    # 総合テスト（複数回実行）
    print("5. 総合パフォーマンステスト（10回実行）...")
    times_cold = []  # キャッシュなし
    times_warm = []  # キャッシュあり
    
    for i in range(10):
        # 奇数回はキャッシュクリア（コールドスタート）
        if i % 2 == 0:
            clear_dashboard_cache(line_id, date_str)
        
        start_time = time.time()
        
        try:
            # ダッシュボードデータ取得
            dashboard_data = get_dashboard_data(line_id, date_str)
            
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000
            
            if i % 2 == 0:
                times_cold.append(execution_time)
                print(f"   実行{i+1} (Cold): {execution_time:.2f}ms")
            else:
                times_warm.append(execution_time)
                print(f"   実行{i+1} (Warm): {execution_time:.2f}ms")
            
        except Exception as e:
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000
            print(f"   実行{i+1}: {execution_time:.2f}ms (エラー: {e})")
    
    print(f"\n=== 結果サマリー ===")
    
    if times_cold:
        avg_cold = sum(times_cold) / len(times_cold)
        print(f"コールドスタート平均: {avg_cold:.2f}ms")
    
    if times_warm:
        avg_warm = sum(times_warm) / len(times_warm)
        print(f"ウォームスタート平均: {avg_warm:.2f}ms")
    
    if times_cold and times_warm:
        improvement = ((avg_cold - avg_warm) / avg_cold) * 100
        print(f"キャッシュ効果: {improvement:.1f}% 改善")
    
    # 全体の平均
    all_times = times_cold + times_warm
    if all_times:
        avg_time = sum(all_times) / len(all_times)
        min_time = min(all_times)
        max_time = max(all_times)
        
        print(f"全体平均実行時間: {avg_time:.2f}ms")
        print(f"最小実行時間: {min_time:.2f}ms")
        print(f"最大実行時間: {max_time:.2f}ms")
        
        # パフォーマンス判定
        if avg_time < 500:  # 0.5秒未満
            print("🎉 パフォーマンス: 優秀（0.5秒未満）")
        elif avg_time < 1000:  # 1秒未満
            print("✅ パフォーマンス: 良好（1秒未満）")
        elif avg_time < 3000:  # 3秒未満
            print("⚠️  パフォーマンス: 要注意（3秒未満）")
        else:
            print("❌ パフォーマンス: 問題あり（3秒以上）")

if __name__ == '__main__':
    test_dashboard_performance()