#!/usr/bin/env python
"""
予測計算パフォーマンステスト

軽量化前後の処理時間を比較測定
"""

import os
import django
import time
from datetime import date, datetime, timedelta

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.models import Line
from production.services.forecast_service import ForecastCalculationService
from production.services.forecast_service_optimized import LightweightForecastService


def benchmark_forecast_calculation(line_id: int, target_date: date, iterations: int = 5):
    """予測計算のベンチマーク"""
    
    print(f"=== 予測計算ベンチマーク ===")
    print(f"ライン: {line_id}, 日付: {target_date}, 反復: {iterations}回")
    print()
    
    # 1. 従来版のテスト
    print("【従来版】ForecastCalculationService")
    original_service = ForecastCalculationService()
    original_times = []
    
    for i in range(iterations):
        start_time = time.time()
        try:
            result = original_service.calculate_completion_forecast(line_id, target_date)
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            original_times.append(processing_time)
            print(f"  実行{i+1}: {processing_time:.2f}ms - {result.get('message', 'OK')}")
        except Exception as e:
            print(f"  実行{i+1}: エラー - {e}")
            original_times.append(999999)  # エラー時は大きな値
    
    print()
    
    # 2. 軽量版のテスト
    print("【軽量版】LightweightForecastService")
    lightweight_service = LightweightForecastService()
    lightweight_times = []
    
    # キャッシュクリアしてフェアな比較
    lightweight_service.clear_cache(line_id, target_date)
    
    for i in range(iterations):
        start_time = time.time()
        try:
            result = lightweight_service.get_forecast_time(line_id, target_date)
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            lightweight_times.append(processing_time)
            print(f"  実行{i+1}: {processing_time:.2f}ms - {result}")
        except Exception as e:
            print(f"  実行{i+1}: エラー - {e}")
            lightweight_times.append(999999)
    
    print()
    
    # 3. 結果比較
    original_avg = sum(original_times) / len(original_times)
    lightweight_avg = sum(lightweight_times) / len(lightweight_times)
    improvement = ((original_avg - lightweight_avg) / original_avg) * 100
    
    print("=== パフォーマンス比較結果 ===")
    print(f"従来版平均: {original_avg:.2f}ms")
    print(f"軽量版平均: {lightweight_avg:.2f}ms")
    print(f"改善率: {improvement:.1f}%")
    
    if improvement > 0:
        print(f"✅ 軽量版が {improvement:.1f}% 高速化されました")
    else:
        print(f"❌ 軽量版が {abs(improvement):.1f}% 遅くなりました")
    
    print()
    return {
        'original_avg': original_avg,
        'lightweight_avg': lightweight_avg,
        'improvement_percent': improvement
    }


def test_cache_effectiveness(line_id: int, target_date: date):
    """キャッシュ効果の測定"""
    
    print("=== キャッシュ効果テスト ===")
    
    service = LightweightForecastService()
    service.clear_cache(line_id, target_date)
    
    # 1回目（キャッシュなし）
    start_time = time.time()
    result1 = service.get_forecast_time(line_id, target_date)
    first_time = (time.time() - start_time) * 1000
    
    # 2回目（キャッシュあり）
    start_time = time.time()
    result2 = service.get_forecast_time(line_id, target_date)
    second_time = (time.time() - start_time) * 1000
    
    cache_improvement = ((first_time - second_time) / first_time) * 100
    
    print(f"1回目（キャッシュなし）: {first_time:.2f}ms")
    print(f"2回目（キャッシュあり）: {second_time:.2f}ms")
    print(f"キャッシュ効果: {cache_improvement:.1f}% 高速化")
    print(f"結果一致: {'✅' if result1 == result2 else '❌'}")
    print()


def run_comprehensive_test():
    """包括的なパフォーマンステスト"""
    
    # テスト対象のラインを取得
    try:
        line = Line.objects.first()
        if not line:
            print("❌ テスト用のラインが見つかりません")
            return
        
        line_id = line.id
        today = date.today()
        
        print(f"📊 予測計算パフォーマンステスト開始")
        print(f"対象ライン: {line.name} (ID: {line_id})")
        print(f"テスト日付: {today}")
        print("=" * 50)
        print()
        
        # 1. 基本ベンチマーク
        benchmark_result = benchmark_forecast_calculation(line_id, today, 3)
        
        # 2. キャッシュ効果テスト
        test_cache_effectiveness(line_id, today)
        
        # 3. パフォーマンス指標取得
        service = LightweightForecastService()
        metrics = service.get_performance_metrics(line_id, today)
        
        print("=== パフォーマンス指標 ===")
        print(f"処理時間: {metrics['processing_time_ms']:.2f}ms")
        print(f"キャッシュヒット: {metrics['cache_hit']}")
        print(f"結果: {metrics['forecast_result']}")
        print()
        
        # 4. 最終評価
        if benchmark_result['improvement_percent'] > 50:
            print("🎉 大幅な性能改善が確認されました！")
        elif benchmark_result['improvement_percent'] > 20:
            print("✅ 良好な性能改善が確認されました")
        elif benchmark_result['improvement_percent'] > 0:
            print("👍 性能改善が確認されました")
        else:
            print("⚠️ 性能改善が見られませんでした")
        
        print(f"📈 総合改善率: {benchmark_result['improvement_percent']:.1f}%")
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")


if __name__ == "__main__":
    run_comprehensive_test()