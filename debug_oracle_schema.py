#!/usr/bin/env python3
"""
Oracle Database Schema Inspector
PRODUCTION_RESULTテーブルの構造を検査し、マイグレーションが正しく適用されたかを確認する
"""

import os
import sys
from datetime import datetime

# Djangoセットアップ
sys.path.append('/home/sano/SandaProject')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')

import django
django.setup()

from django.db import connections
from django.db.utils import OperationalError


class OracleSchemaInspector:
    """Oracle データベースのスキーマ検査クラス"""
    
    def __init__(self):
        self.connection = None
        self.table_name = 'PRODUCTION_RESULT'
        
    def connect_to_oracle(self):
        """Oracleデータベースに接続"""
        try:
            self.connection = connections['oracle']
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                result = cursor.fetchone()
                print(f"✅ Oracle接続成功: {result}")
                return True
        except OperationalError as e:
            print(f"❌ Oracle接続エラー: {e}")
            return False
        except Exception as e:
            print(f"❌ 予期しないエラー: {e}")
            return False
    
    def check_table_exists(self):
        """テーブルの存在確認"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM USER_TABLES 
                    WHERE TABLE_NAME = %s
                """, [self.table_name])
                
                count = cursor.fetchone()[0]
                exists = count > 0
                print(f"{'✅' if exists else '❌'} テーブル '{self.table_name}' 存在確認: {exists}")
                return exists
        except Exception as e:
            print(f"❌ テーブル存在確認エラー: {e}")
            return False
    
    def inspect_table_structure(self):
        """テーブル構造の詳細検査"""
        print(f"\n=== {self.table_name} テーブル構造検査 ===")
        
        try:
            # カラム情報を取得
            with self.connection.cursor() as cursor:
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
                    WHERE TABLE_NAME = %s
                    ORDER BY COLUMN_ID
                """, [self.table_name])
                
                columns = cursor.fetchall()
                
                if not columns:
                    print(f"❌ テーブル '{self.table_name}' のカラム情報が見つかりません")
                    return False
                
                print(f"\n📋 カラム情報 (総数: {len(columns)})")
                print("-" * 80)
                print(f"{'カラム名':<20} {'データ型':<15} {'長さ':<8} {'NULL可':<8} {'デフォルト値'}")
                print("-" * 80)
                
                target_columns = {'LINE_ID', 'MACHINE_ID', 'PART_ID', 'LINE', 'MACHINE', 'PART'}
                found_columns = {}
                
                for col in columns:
                    col_name, data_type, length, precision, scale, nullable, default = col
                    
                    # 数値型の場合は精度も表示
                    if data_type == 'NUMBER' and precision:
                        type_info = f"{data_type}({precision},{scale or 0})"
                    elif length:
                        type_info = f"{data_type}({length})"
                    else:
                        type_info = data_type
                    
                    nullable_str = "YES" if nullable == 'Y' else "NO"
                    default_str = str(default)[:15] if default else ""
                    
                    print(f"{col_name:<20} {type_info:<15} {length or '':<8} {nullable_str:<8} {default_str}")
                    
                    # 対象カラムの記録
                    if col_name in target_columns:
                        found_columns[col_name] = {
                            'data_type': data_type,
                            'nullable': nullable == 'Y',
                            'default': default
                        }
                
                print("-" * 80)
                return found_columns
                
        except Exception as e:
            print(f"❌ テーブル構造検査エラー: {e}")
            return False
    
    def check_constraints(self):
        """制約の確認"""
        print(f"\n=== {self.table_name} 制約検査 ===")
        
        try:
            with self.connection.cursor() as cursor:
                # NOT NULL制約の確認
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME,
                        NULLABLE
                    FROM USER_TAB_COLUMNS 
                    WHERE TABLE_NAME = %s
                    AND COLUMN_NAME IN ('LINE_ID', 'MACHINE_ID', 'PART_ID', 'LINE', 'MACHINE', 'PART')
                    ORDER BY COLUMN_NAME
                """, [self.table_name])
                
                constraints = cursor.fetchall()
                
                print("🔒 NULL制約状況:")
                print("-" * 40)
                for col_name, nullable in constraints:
                    nullable_str = "NULL可" if nullable == 'Y' else "NOT NULL"
                    status = "✅" if nullable == 'Y' else "⚠️"
                    print(f"{status} {col_name:<15}: {nullable_str}")
                
                # CHECK制約の確認
                cursor.execute("""
                    SELECT 
                        CONSTRAINT_NAME,
                        SEARCH_CONDITION
                    FROM USER_CONSTRAINTS 
                    WHERE TABLE_NAME = %s
                    AND CONSTRAINT_TYPE = 'C'
                    AND SEARCH_CONDITION IS NOT NULL
                """, [self.table_name])
                
                check_constraints = cursor.fetchall()
                
                if check_constraints:
                    print(f"\n🔍 CHECK制約 (総数: {len(check_constraints)}):")
                    print("-" * 60)
                    for constraint_name, condition in check_constraints:
                        print(f"📌 {constraint_name}: {condition}")
                
                return True
                
        except Exception as e:
            print(f"❌ 制約検査エラー: {e}")
            return False
    
    def check_indexes(self):
        """インデックスの確認"""
        print(f"\n=== {self.table_name} インデックス検査 ===")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        INDEX_NAME,
                        UNIQUENESS,
                        STATUS
                    FROM USER_INDEXES 
                    WHERE TABLE_NAME = %s
                    ORDER BY INDEX_NAME
                """, [self.table_name])
                
                indexes = cursor.fetchall()
                
                if indexes:
                    print(f"📇 インデックス (総数: {len(indexes)}):")
                    print("-" * 50)
                    for index_name, uniqueness, status in indexes:
                        unique_str = "UNIQUE" if uniqueness == 'UNIQUE' else "NON-UNIQUE"
                        print(f"📌 {index_name}: {unique_str} ({status})")
                else:
                    print("ℹ️  インデックスが見つかりません")
                
                return True
                
        except Exception as e:
            print(f"❌ インデックス検査エラー: {e}")
            return False
    
    def verify_migration_success(self, found_columns):
        """マイグレーション成功の検証"""
        print(f"\n=== マイグレーション検証 ===")
        
        # 期待されるカラム構造
        expected_structure = {
            'LINE': {'nullable': True, 'data_type': 'VARCHAR2'},
            'MACHINE': {'nullable': True, 'data_type': 'VARCHAR2'},
            'PART': {'nullable': True, 'data_type': 'VARCHAR2'},
            'LINE_ID': {'nullable': True, 'data_type': 'NUMBER'},
            'MACHINE_ID': {'nullable': True, 'data_type': 'NUMBER'},
            'PART_ID': {'nullable': True, 'data_type': 'NUMBER'},
        }
        
        success = True
        
        print("🔍 マイグレーション結果検証:")
        print("-" * 50)
        
        for col_name, expected in expected_structure.items():
            if col_name in found_columns:
                actual = found_columns[col_name]
                
                # NULL制約の確認
                null_ok = actual['nullable'] == expected['nullable']
                null_status = "✅" if null_ok else "❌"
                
                # データ型の確認
                type_ok = actual['data_type'] == expected['data_type']
                type_status = "✅" if type_ok else "❌"
                
                print(f"{col_name}:")
                print(f"  {null_status} NULL制約: {'期待通り' if null_ok else '期待と異なる'} (実際: {'NULL可' if actual['nullable'] else 'NOT NULL'})")
                print(f"  {type_status} データ型: {'期待通り' if type_ok else '期待と異なる'} (実際: {actual['data_type']})")
                
                if not (null_ok and type_ok):
                    success = False
            else:
                print(f"❌ {col_name}: カラムが見つかりません")
                success = False
        
        return success
    
    def run_complete_inspection(self):
        """完全な検査の実行"""
        print("=" * 80)
        print("🔍 ORACLE DATABASE SCHEMA INSPECTOR")
        print(f"📅 実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 1. 接続テスト
        if not self.connect_to_oracle():
            return False
        
        # 2. テーブル存在確認
        if not self.check_table_exists():
            return False
        
        # 3. テーブル構造検査
        found_columns = self.inspect_table_structure()
        if not found_columns:
            return False
        
        # 4. 制約確認
        self.check_constraints()
        
        # 5. インデックス確認
        self.check_indexes()
        
        # 6. マイグレーション検証
        migration_success = self.verify_migration_success(found_columns)
        
        # 7. 結果サマリー
        print(f"\n{'=' * 80}")
        print("📊 検査結果サマリー")
        print(f"{'=' * 80}")
        
        if migration_success:
            print("🎉 マイグレーション成功! テーブル構造が期待通りです。")
        else:
            print("⚠️  マイグレーションに問題があります。上記の詳細を確認してください。")
        
        return migration_success


def main():
    """メイン実行関数"""
    inspector = OracleSchemaInspector()
    try:
        inspector.run_complete_inspection()
    except KeyboardInterrupt:
        print("\n\n⚠️  ユーザーによって中断されました")
    except Exception as e:
        print(f"\n\n❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()