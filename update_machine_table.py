#!/usr/bin/env python
"""
Machineテーブル更新スクリプト
STA_NO3.csvの内容をMachineテーブルに反映する
"""
import os
import sys
import django
import csv
from pathlib import Path

# Djangoプロジェクトのパスを追加
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Djangoの設定を読み込み
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from production.models import Line, Machine
from django.core.management.color import make_style

style = make_style()

def update_machine_table():
    """Machineテーブルを更新する"""
    print(style.HTTP_INFO("Machineテーブル更新処理を開始します..."))
    
    # CSVファイルのパス
    csv_file_path = Path(__file__).parent / "STA_NO3.csv"
    
    if not csv_file_path.exists():
        print(style.ERROR(f"CSVファイルが見つかりません: {csv_file_path}"))
        return False
    
    try:
        # 1. 既存のMachineデータを削除
        print(style.HTTP_INFO("1. 既存Machineデータを削除中..."))
        deleted_count = Machine.objects.all().delete()[0]
        print(f"   削除された設備数: {deleted_count}")
        
        # 2. Lineテーブルの情報を取得（外部キー用）
        print(style.HTTP_INFO("2. Lineテーブル情報を取得中..."))
        lines_dict = {}
        for line in Line.objects.all():
            lines_dict[line.name] = line
        print(f"   利用可能ライン数: {len(lines_dict)}")
        
        # 3. CSVファイルを読み込んで処理
        print(style.HTTP_INFO("3. CSVデータを読み込み中..."))
        
        created_count = 0
        error_count = 0
        missing_lines = set()
        
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            # ヘッダー情報をデバッグ出力
            print(f"   CSVヘッダー: {csv_reader.fieldnames}")
            
            for row_num, row in enumerate(csv_reader, start=2):  # ヘッダー行の次から
                # デバッグ: 行の内容を確認
                if row_num <= 5:
                    print(f"   行{row_num}データ: {dict(row)}")
                
                # 行が空または不完全な場合をチェック
                if not row or all(not v.strip() if v else True for v in row.values()):
                    print(f"   行{row_num}: 空行をスキップ")
                    continue
                
                # 必要な列が存在するかチェック
                if 'line' not in row or 'name' not in row or 'description' not in row:
                    print(style.ERROR(f"   行{row_num}: 必要な列が不足 - 利用可能列: {list(row.keys())}"))
                    error_count += 1
                    continue
                
                line_name = row['line'].strip() if row['line'] else ''
                machine_name = row['name'].strip() if row['name'] else ''
                description = row['description'].strip() if row['description'] else ''
                
                # 空行をスキップ
                if not line_name or not machine_name:
                    print(f"   行{row_num}: 空データをスキップ (line='{line_name}', name='{machine_name}')")
                    continue
                
                # 対応するLineオブジェクトを取得
                if line_name not in lines_dict:
                    missing_lines.add(line_name)
                    error_count += 1
                    print(style.ERROR(f"   行{row_num}: ライン '{line_name}' が見つかりません"))
                    continue
                
                try:
                    # Machineオブジェクトを作成
                    machine = Machine.objects.create(
                        name=machine_name,
                        line=lines_dict[line_name],
                        description=description,
                        is_active=True,  # 要求通りTrueに設定
                        is_production_active=True  # 要求通りTrueに設定
                    )
                    created_count += 1
                    
                    if created_count <= 5:  # 最初の5件のみ詳細表示
                        print(f"   追加: {line_name} - {machine_name} - {description}")
                    elif created_count == 6:
                        print("   ... (詳細表示を省略)")
                        
                except Exception as e:
                    error_count += 1
                    print(style.ERROR(f"   行{row_num}: 設備作成エラー - {str(e)}"))
        
        # 4. 結果サマリー
        print(f"\n✓ 処理完了:")
        print(f"   作成された設備数: {created_count}")
        print(f"   エラー数: {error_count}")
        
        if missing_lines:
            print(style.WARNING(f"\n⚠️  見つからなかったライン ({len(missing_lines)}件):"))
            for line_name in sorted(missing_lines):
                print(f"     - {line_name}")
        
        # 5. 更新後のMachineテーブル確認
        print(style.HTTP_INFO("\n4. 更新後のMachineテーブル確認:"))
        total_machines = Machine.objects.count()
        print(f"   総設備数: {total_machines}")
        
        # ライン別統計
        from django.db.models import Count
        line_stats = Machine.objects.values('line__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        print(f"\n   ライン別設備数（上位10ライン）:")
        for stat in line_stats:
            print(f"     {stat['line__name']}: {stat['count']}台")
        
        # 設定確認
        active_count = Machine.objects.filter(is_active=True).count()
        production_active_count = Machine.objects.filter(is_production_active=True).count()
        print(f"\n   is_active=True: {active_count}台")
        print(f"   is_production_active=True: {production_active_count}台")
        
        return error_count == 0
        
    except Exception as e:
        print(style.ERROR(f"✗ 処理中にエラーが発生しました: {str(e)}"))
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = update_machine_table()
    if success:
        print(style.SUCCESS("\n🎉 Machineテーブルの更新が正常に完了しました！"))
    else:
        print(style.ERROR("\n❌ Machineテーブルの更新中にエラーが発生しました"))
    
    sys.exit(0 if success else 1)