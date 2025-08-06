#!/usr/bin/env python
"""
OracleのPRODUCTION_RESULTテーブルを整数IDから文字列フィールドに変換する
"""
import os
import sys
import django

# Djangoプロジェクトの設定を読み込み
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from django.db import connections
from production.models import Line, Machine, Part

def migrate_oracle_table():
    """OracleテーブルをIDフィールドから文字列フィールドに変換"""
    oracle_db = connections['oracle']
    postgres_db = connections['default']
    
    try:
        print("=== Oracle PRODUCTION_RESULT テーブル構造変更開始 ===")
        
        with oracle_db.cursor() as cursor:
            # 1. 新しい文字列カラムを追加
            print("1. 新しい文字列カラムを追加中...")
            try:
                cursor.execute("ALTER TABLE production_result ADD (line NVARCHAR2(100))")
                print("   LINE カラム追加完了")
            except Exception as e:
                if "ORA-01430" in str(e):  # column already exists
                    print("   LINE カラムは既に存在します")
                else:
                    raise
            
            try:
                cursor.execute("ALTER TABLE production_result ADD (machine NVARCHAR2(100))")
                print("   MACHINE カラム追加完了")
            except Exception as e:
                if "ORA-01430" in str(e):
                    print("   MACHINE カラムは既に存在します")
                else:
                    raise
            
            try:
                cursor.execute("ALTER TABLE production_result ADD (part NVARCHAR2(100))")
                print("   PART カラム追加完了")
            except Exception as e:
                if "ORA-01430" in str(e):
                    print("   PART カラムは既に存在します")
                else:
                    raise
        
        # 2. PostgreSQLから名前を取得してマッピングを作成
        print("2. PostgreSQLから名前マッピングを取得中...")
        line_mapping = {}
        machine_mapping = {}
        part_mapping = {}
        
        for line in Line.objects.all():
            line_mapping[line.id] = line.name
        
        for machine in Machine.objects.all():
            machine_mapping[machine.id] = machine.name
        
        for part in Part.objects.all():
            part_mapping[part.id] = part.name
        
        print(f"   ライン: {len(line_mapping)}件")
        print(f"   設備: {len(machine_mapping)}件") 
        print(f"   機種: {len(part_mapping)}件")
        
        # 3. データを変換
        print("3. データ変換中...")
        with oracle_db.cursor() as cursor:
            # 変換対象のレコードを取得
            cursor.execute("""
                SELECT id, line_id, machine_id, part_id 
                FROM production_result 
                WHERE line IS NULL OR machine IS NULL OR part IS NULL
            """)
            
            records = cursor.fetchall()
            print(f"   変換対象: {len(records)}件")
            
            converted_count = 0
            error_count = 0
            
            for record in records:
                record_id, line_id, machine_id, part_id = record
                
                try:
                    line_name = line_mapping.get(line_id, f"UNKNOWN_LINE_{line_id}")
                    machine_name = machine_mapping.get(machine_id, f"UNKNOWN_MACHINE_{machine_id}")
                    part_name = part_mapping.get(part_id, f"UNKNOWN_PART_{part_id}")
                    
                    cursor.execute("""
                        UPDATE production_result 
                        SET line = :line_name, machine = :machine_name, part = :part_name
                        WHERE id = :record_id
                    """, {
                        'line_name': line_name,
                        'machine_name': machine_name, 
                        'part_name': part_name,
                        'record_id': record_id
                    })
                    
                    converted_count += 1
                    
                    if converted_count % 100 == 0:
                        print(f"   進捗: {converted_count}/{len(records)}")
                        
                except Exception as e:
                    print(f"   エラー (ID: {record_id}): {e}")
                    error_count += 1
            
            oracle_db.commit()
            print(f"   変換完了: {converted_count}件, エラー: {error_count}件")
        
        # 4. 変換結果を確認
        print("4. 変換結果確認...")
        with oracle_db.cursor() as cursor:
            cursor.execute("""
                SELECT line, machine, part, COUNT(*) 
                FROM production_result 
                GROUP BY line, machine, part
                ORDER BY COUNT(*) DESC
            """)
            
            results = cursor.fetchall()
            print("   トップ5組み合わせ:")
            for i, (line, machine, part, count) in enumerate(results[:5]):
                print(f"   {i+1}. {line} - {machine} - {part}: {count}件")
        
        print("\n=== 変換完了 ===")
        print("注意: 古いIDカラム(LINE_ID, MACHINE_ID, PART_ID)はまだ残っています")
        print("動作確認後、手動で削除してください")
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_oracle_table()