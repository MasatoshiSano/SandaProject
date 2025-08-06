#!/usr/bin/env python
import os
import sys
import django

# Djangoプロジェクトの設定を読み込み
sys.path.append('/home/sano/SandaDev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.models import Result, Line

def test_result_model():
    """修正されたResultモデルのテスト"""
    try:
        print("=== Resultモデルテスト ===")
        
        # Line 1のResultデータを取得
        results = Result.objects.filter(line_id=1)[:5]
        print(f"Line 1の実績データ数（最初の5件）: {len(results)}")
        
        for result in results:
            try:
                print(f"ID: {result.id}, Line: {result.line.name}, Part: {result.part.name}, Time: {result.timestamp}")
            except Exception as e:
                print(f"Error accessing related data: {e}")
                print(f"Raw data - ID: {result.id}, LineID: {result.line_id}, PartID: {result.part_id}")
        
        # 総件数確認
        total_count = Result.objects.count()
        print(f"\n実績データ総件数: {total_count}")
        
    except Exception as e:
        print(f"テストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_result_model()