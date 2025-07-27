#!/usr/bin/env python3
"""
Simple Oracle Database Inspector
Djangoを使わずに直接Oracleに接続してテーブル構造を確認する
"""

import sys
from datetime import datetime

def check_oracledb_availability():
    """oracledbライブラリの利用可能性をチェック"""
    try:
        import oracledb
        print(f"✅ oracledb利用可能 (バージョン: {oracledb.__version__})")
        return True, oracledb
    except ImportError:
        print("❌ oracledbライブラリが見つかりません")
        print("インストール方法: pip install oracledb>=2.3.0")
        return False, None

def connect_to_oracle(oracledb_module):
    """Oracleデータベースに直接接続"""
    # Docker環境の接続設定
    connection_params = {
        'user': 'system',
        'password': 'oracle123',
        'dsn': 'oracle:1521/XEPDB1'
    }
    
    try:
        print("🔌 Oracle接続試行中...")
        print(f"   DSN: {connection_params['dsn']}")
        print(f"   User: {connection_params['user']}")
        
        connection = oracledb_module.connect(**connection_params)
        print("✅ Oracle接続成功")
        return connection
    except Exception as e:
        print(f"❌ Oracle接続エラー: {e}")
        return None

def inspect_table_structure(connection, table_name='PRODUCTION_RESULT'):
    """テーブル構造の検査"""
    print(f"\n=== {table_name} テーブル構造検査 ===")
    
    try:
        cursor = connection.cursor()
        
        # テーブルの存在確認
        cursor.execute("""
            SELECT COUNT(*) 
            FROM USER_TABLES 
            WHERE TABLE_NAME = :table_name
        """, {'table_name': table_name})
        
        count = cursor.fetchone()[0]
        if count == 0:
            print(f"❌ テーブル '{table_name}' が見つかりません")
            return False
        
        print(f"✅ テーブル '{table_name}' が存在します")
        
        # カラム情報の取得
        cursor.execute("""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                DATA_LENGTH,
                DATA_PRECISION,
                DATA_SCALE,
                NULLABLE,
                DATA_DEFAULT
            FROM USER_TAB_COLUMNS 
            WHERE TABLE_NAME = :table_name
            ORDER BY COLUMN_ID
        """, {'table_name': table_name})
        
        columns = cursor.fetchall()
        
        print(f"\n📋 カラム情報 (総数: {len(columns)})")
        print("-" * 85)
        print(f"{'カラム名':<20} {'データ型':<15} {'長さ':<8} {'精度':<6} {'NULL可':<8} {'デフォルト値'}")
        print("-" * 85)
        
        target_columns = {'LINE_ID', 'MACHINE_ID', 'PART_ID', 'LINE', 'MACHINE', 'PART'}
        found_columns = {}
        
        for col in columns:
            col_name, data_type, length, precision, scale, nullable, default = col
            
            # データ型情報の整形
            if data_type == 'NUMBER' and precision:
                type_info = f"{data_type}({precision},{scale or 0})"
            elif length and data_type in ['VARCHAR2', 'CHAR']:
                type_info = f"{data_type}({length})"
            else:
                type_info = data_type
            
            nullable_str = "YES" if nullable == 'Y' else "NO"
            precision_str = str(precision) if precision else ""
            default_str = str(default)[:10] if default else ""
            
            print(f"{col_name:<20} {type_info:<15} {length or '':<8} {precision_str:<6} {nullable_str:<8} {default_str}")
            
            # 対象カラムの記録
            if col_name in target_columns:
                found_columns[col_name] = {
                    'data_type': data_type,
                    'nullable': nullable == 'Y',
                    'default': default
                }
        
        print("-" * 85)
        
        # 制約情報の確認
        print(f"\n🔒 制約情報:")
        cursor.execute("""
            SELECT 
                COLUMN_NAME,
                NULLABLE
            FROM USER_TAB_COLUMNS 
            WHERE TABLE_NAME = :table_name
            AND COLUMN_NAME IN ('LINE_ID', 'MACHINE_ID', 'PART_ID', 'LINE', 'MACHINE', 'PART')
            ORDER BY COLUMN_NAME
        """, {'table_name': table_name})
        
        constraints = cursor.fetchall()
        print("-" * 40)
        for col_name, nullable in constraints:
            nullable_str = "NULL可" if nullable == 'Y' else "NOT NULL"
            status = "✅" if nullable == 'Y' else "⚠️"
            print(f"{status} {col_name:<15}: {nullable_str}")
        
        # マイグレーション結果の検証
        print(f"\n=== マイグレーション検証 ===")
        expected_nullable_columns = {'LINE', 'MACHINE', 'PART', 'LINE_ID', 'MACHINE_ID', 'PART_ID'}
        
        migration_success = True
        for col_name, nullable in constraints:
            if col_name in expected_nullable_columns:
                is_nullable = nullable == 'Y'
                if is_nullable:
                    print(f"✅ {col_name}: NULL制約が正しく削除されています")
                else:
                    print(f"❌ {col_name}: まだNOT NULL制約が残っています")
                    migration_success = False
        
        return migration_success, found_columns
        
    except Exception as e:
        print(f"❌ テーブル構造検査エラー: {e}")
        return False, {}
    finally:
        if 'cursor' in locals():
            cursor.close()

def check_table_data_sample(connection, table_name='PRODUCTION_RESULT'):
    """テーブルのサンプルデータ確認"""
    print(f"\n=== {table_name} サンプルデータ ===")
    
    try:
        cursor = connection.cursor()
        
        # データ件数の確認
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"📊 総レコード数: {count}")
        
        if count > 0:
            # サンプルデータの取得
            cursor.execute(f"""
                SELECT * FROM {table_name} 
                WHERE ROWNUM <= 3
                ORDER BY ID
            """)
            
            # カラム名の取得
            columns = [desc[0] for desc in cursor.description]
            print(f"\n📝 サンプルデータ (最大3件):")
            print("-" * 120)
            print(" | ".join(f"{col:<12}" for col in columns))
            print("-" * 120)
            
            rows = cursor.fetchall()
            for row in rows:
                print(" | ".join(f"{str(val):<12}" for val in row))
        
    except Exception as e:
        print(f"❌ サンプルデータ取得エラー: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()

def main():
    """メイン実行関数"""
    print("=" * 80)
    print("🔍 SIMPLE ORACLE DATABASE INSPECTOR")
    print(f"📅 実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. oracledbライブラリのチェック
    available, oracledb_module = check_oracledb_availability()
    if not available:
        return False
    
    # 2. Oracle接続
    connection = connect_to_oracle(oracledb_module)
    if not connection:
        return False
    
    try:
        # 3. テーブル構造検査
        migration_success, found_columns = inspect_table_structure(connection)
        
        # 4. サンプルデータ確認
        check_table_data_sample(connection)
        
        # 5. 結果サマリー
        print(f"\n{'=' * 80}")
        print("📊 検査結果サマリー")
        print(f"{'=' * 80}")
        
        if migration_success:
            print("🎉 マイグレーション成功! NULL制約が正しく削除されています。")
        else:
            print("⚠️  マイグレーションに問題があります。一部のカラムにまだNOT NULL制約が残っています。")
        
        print(f"\n📋 検出されたカラム構造:")
        for col_name, info in found_columns.items():
            print(f"  • {col_name}: {info['data_type']} ({'NULL可' if info['nullable'] else 'NOT NULL'})")
        
        return migration_success
        
    finally:
        connection.close()
        print(f"\n🔌 Oracle接続を閉じました")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  ユーザーによって中断されました")
    except Exception as e:
        print(f"\n\n❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()