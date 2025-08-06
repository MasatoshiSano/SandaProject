#!/usr/bin/env python
"""
Machineテーブルの更新スクリプト
- 既存のMachineレコードを削除
- STA_NO3.csvの内容を新しいMachineレコードとして挿入
"""

import os
import sys
import django
import csv
from pathlib import Path

# Django設定
sys.path.append('/home/sano/SandaDev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.models import Machine, Line


def clear_machine_table():
    """既存のMachineレコードを削除"""
    print("Machineテーブルをクリア中...")
    deleted_count = Machine.objects.count()
    Machine.objects.all().delete()
    print(f"{deleted_count}件のレコードを削除しました。")


def get_or_create_line(line_name):
    """Lineオブジェクトを取得または作成"""
    line, created = Line.objects.get_or_create(
        name=line_name,
        defaults={
            'description': f'{line_name}ライン',
            'is_active': True
        }
    )
    if created:
        print(f"新しいライン '{line_name}' を作成しました。")
    return line


def load_csv_data():
    """CSVファイルからデータを読み込んでMachineレコードを作成"""
    csv_file_path = '/home/sano/SandaDev/STA_NO3.csv'
    
    if not Path(csv_file_path).exists():
        print(f"CSVファイルが見つかりません: {csv_file_path}")
        return
    
    print(f"CSVファイルを読み込み中: {csv_file_path}")
    
    created_count = 0
    with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            line_name = row['line'].strip()
            machine_name = row['name'].strip()
            description = row['description'].strip()
            
            # Lineオブジェクトを取得または作成
            line = get_or_create_line(line_name)
            
            # Machineオブジェクトを作成
            machine = Machine.objects.create(
                name=machine_name,
                line=line,
                description=description,
                is_active=True,
                is_production_active=True
            )
            
            created_count += 1
            if created_count % 100 == 0:
                print(f"{created_count}件のMachineレコードを作成しました...")
    
    print(f"合計 {created_count}件のMachineレコードを作成しました。")


def main():
    """メイン処理"""
    print("=== Machineテーブル更新開始 ===")
    
    try:
        # 既存データを削除
        clear_machine_table()
        
        # CSVデータを読み込み
        load_csv_data()
        
        print("=== Machineテーブル更新完了 ===")
        
        # 結果確認
        total_machines = Machine.objects.count()
        total_lines = Line.objects.count()
        print(f"現在のMachine数: {total_machines}")
        print(f"現在のLine数: {total_lines}")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()