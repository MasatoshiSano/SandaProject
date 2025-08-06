#!/usr/bin/env python
import os
import sys
import django

# Djangoプロジェクトの設定を読み込み
sys.path.append('/home/sano/SandaDev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')
django.setup()

from django.db import connections, DatabaseError

def check_oracle_tables():
    """Oracleデータベースのテーブル構造を確認"""
    try:
        oracle_connection = connections['oracle']
        
        with oracle_connection.cursor() as cursor:
            # テーブル一覧取得
            print("=== Oracle テーブル一覧 ===")
            cursor.execute("""
                SELECT table_name 
                FROM user_tables 
                WHERE table_name LIKE '%RESULT%' OR table_name LIKE '%PRODUCTION%'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            for table in tables:
                print(f"テーブル: {table[0]}")
            
            # production_resultテーブルの列構造確認
            print("\n=== PRODUCTION_RESULT テーブル構造 ===")
            cursor.execute("""
                SELECT column_name, data_type, nullable, data_length
                FROM user_tab_columns 
                WHERE table_name = 'PRODUCTION_RESULT'
                ORDER BY column_id
            """)
            columns = cursor.fetchall()
            if columns:
                for col in columns:
                    print(f"列: {col[0]}, 型: {col[1]}, NULL許可: {col[2]}, 長さ: {col[3]}")
            else:
                print("PRODUCTION_RESULT テーブルが見つかりません")
                
            # 代替テーブル名確認
            print("\n=== RESULT関連テーブル確認 ===")
            cursor.execute("""
                SELECT table_name 
                FROM user_tables 
                WHERE table_name LIKE '%RESULT%'
                ORDER BY table_name
            """)
            result_tables = cursor.fetchall()
            for table in result_tables:
                table_name = table[0]
                print(f"\n--- {table_name} テーブル構造 ---")
                cursor.execute(f"""
                    SELECT column_name, data_type 
                    FROM user_tab_columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY column_id
                """)
                cols = cursor.fetchall()
                for col in cols:
                    print(f"  {col[0]}: {col[1]}")
                    
            # シーケンス確認
            print("\n=== シーケンス確認 ===")
            cursor.execute("""
                SELECT sequence_name 
                FROM user_sequences 
                WHERE sequence_name LIKE '%RESULT%' OR sequence_name LIKE '%PRODUCTION%'
                ORDER BY sequence_name
            """)
            sequences = cursor.fetchall()
            if sequences:
                for seq in sequences:
                    print(f"シーケンス: {seq[0]}")
            else:
                print("関連するシーケンスが見つかりません")

    except DatabaseError as e:
        print(f"データベースエラー: {e}")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    check_oracle_tables()