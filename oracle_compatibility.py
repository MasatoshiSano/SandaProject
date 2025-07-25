"""
Oracle Database Compatibility Module
cx_Oracle → oracledb migration compatibility for Django
"""

import sys
import oracledb

# oracledbバージョンをcx_Oracleバージョン形式で設定
oracledb.version = "8.3.0"

# Django Oracle backendのためのcx_Oracleモジュール互換性
sys.modules["cx_Oracle"] = oracledb

print(f"✅ Oracle compatibility layer loaded: oracledb {oracledb.__version__} as cx_Oracle")