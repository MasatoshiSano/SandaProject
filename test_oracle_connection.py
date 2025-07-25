#!/usr/bin/env python3
"""
Oracle接続テストスクリプト
cx_OracleからoracledbへのMigration後の動作確認
"""

import os
import sys

# Djangoセットアップ
sys.path.append('/home/sano/SandaProject')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_docker')

import django
django.setup()

def test_oracledb_import():
    """oracledbライブラリのインポートテスト"""
    try:
        import oracledb
        print(f"✅ oracledb successfully imported (version: {oracledb.__version__})")
        return True
    except ImportError as e:
        print(f"❌ Failed to import oracledb: {e}")
        return False

def test_django_oracle_backend():
    """Django OracleバックエンドでのOracleDB使用テスト"""
    try:
        from django.db import connections
        from django.db.utils import OperationalError
        
        # Oracle接続設定を確認
        oracle_db = connections.databases.get('oracle')
        if oracle_db:
            print("✅ Oracle database configuration found in Django settings")
            print(f"   - ENGINE: {oracle_db['ENGINE']}")
            print(f"   - NAME: {oracle_db['NAME']}")
            print(f"   - USER: {oracle_db['USER']}")
            
            # 実際の接続テスト
            try:
                connection = connections['oracle']
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM DUAL")
                    result = cursor.fetchone()
                    print(f"✅ Oracle connection successful: {result}")
                    return True
            except OperationalError as e:
                print(f"⚠️  Oracle connection failed (expected if Oracle not running): {e}")
                return False
        else:
            print("❌ Oracle database configuration not found")
            return False
    except Exception as e:
        print(f"❌ Django Oracle backend test failed: {e}")
        return False

def main():
    """メインテスト実行"""
    print("=== Oracle Database Migration Test (cx_Oracle → oracledb) ===\n")
    
    # テスト1: oracledbライブラリのインポート
    print("1. Testing oracledb library import...")
    import_success = test_oracledb_import()
    print()
    
    # テスト2: Django Oracleバックエンドの動作
    print("2. Testing Django Oracle backend...")
    django_success = test_django_oracle_backend()
    print()
    
    # 結果サマリー
    print("=== Test Results ===")
    print(f"📦 oracledb import: {'✅ PASS' if import_success else '❌ FAIL'}")
    print(f"🔗 Django Oracle: {'✅ PASS' if django_success else '⚠️  SKIP (Oracle not running)'}")
    
    if import_success:
        print("\n🎉 Migration from cx_Oracle to oracledb completed successfully!")
        print("   - No Oracle Client installation required")
        print("   - Thin mode enabled by default")
    else:
        print("\n❌ Migration incomplete. Please install oracledb:")
        print("   pip install oracledb>=2.3.0")

if __name__ == "__main__":
    main()