#!/usr/bin/env python
import os
import sys
import django

# Djangoプロジェクトの設定を読み込み
sys.path.append('/home/sano/SandaDev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.models import Line, Result

def check_lines_and_results():
    """Line情報とResult分布を確認"""
    try:
        print("=== Line一覧 ===")
        lines = Line.objects.all()
        for line in lines:
            print(f"ID: {line.id}, Name: {line.name}")
        
        print("\n=== Result分布 ===")
        from django.db.models import Count
        result_by_line = Result.objects.values('line_id').annotate(count=Count('id')).order_by('line_id')
        for item in result_by_line:
            try:
                line = Line.objects.get(id=item['line_id'])
                print(f"Line ID: {item['line_id']} ({line.name}): {item['count']}件")
            except Line.DoesNotExist:
                print(f"Line ID: {item['line_id']} (名前不明): {item['count']}件")
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_lines_and_results()