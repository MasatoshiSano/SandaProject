#!/usr/bin/env python
import os
import sys
import django

# Djangoプロジェクトの設定を読み込み
sys.path.append('/home/sano/SandaDev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.models import Result, Line

def test_corrected_result_model():
    """修正されたResultモデルのテスト"""
    try:
        print("=== 修正後Resultモデルテスト ===")
        
        # Line 3のResultデータを取得（カスタムマネージャー使用）
        line3 = Line.objects.get(id=3)
        print(f"Line 3: {line3.name}")
        
        results = Result.objects.filter_by_line_name(line3.name)[:3]
        print(f"Line 3の実績データ数（最初の3件）: {len(results)}")
        
        for result in results:
            print(f"ID: {result.id}, Line: {result.line_name}, Part: {result.part_name}, Time: {result.timestamp}")
        
        # 直接IDでのフィルタも確認
        direct_results = Result.objects.filter(line_id=3)[:3]
        print(f"\n直接line_idでフィルタ（最初の3件）: {len(direct_results)}")
        
        for result in direct_results:
            print(f"ID: {result.id}, LineID: {result.line_id}, Line名: {result.line_name}")
        
        print(f"\n実績データ総件数: {Result.objects.count()}")
        
    except Exception as e:
        print(f"テストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_corrected_result_model()