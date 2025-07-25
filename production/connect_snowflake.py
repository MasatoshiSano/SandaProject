import os
import snowflake.connector
from contextlib import contextmanager

# プロキシの環境変数を設定
os.environ['HTTP_PROXY'] = 'http://hime-proxy-srv.hime.melco.co.jp:9515'
os.environ['HTTPS_PROXY'] = 'http://hime-proxy-srv.hime.melco.co.jp:9515'

# Snowflakeの接続設定
db_config = {
    'user': 'zhh001r_00_hime',
    'password': 'Zhh001r_00_hime_99',
    'account': 'rb73083.japan-east.azure',
    'warehouse': 'HIME_01_XS',
    'database': 'ILE01',
    'schema': 'ZHH001'
}

@contextmanager
def get_snowflake_connection():
    """
    Snowflakeへの接続を提供するコンテキストマネージャ
    
    使用例:
    with get_snowflake_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM table")
        results = cursor.fetchall()
    """
    conn = snowflake.connector.connect(
        user=db_config['user'],
        password=db_config['password'],
        account=db_config['account'],
        warehouse=db_config['warehouse'],
        database=db_config['database'],
        schema=db_config['schema']
    )
    try:
        yield conn
    finally:
        conn.close() 