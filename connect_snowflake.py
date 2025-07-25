import os
import snowflake.connector

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

# 接続を作成
conn = snowflake.connector.connect(
    user=db_config['user'],
    password=db_config['password'],
    account=db_config['account'],
    warehouse=db_config['warehouse'],
    database=db_config['database'],
    schema=db_config['schema']
)

# クエリの実行例
cursor = conn.cursor()
try:
    cursor.execute("SELECT CURRENT_VERSION()")  # Snowflakeのバージョンを確認
    result = cursor.fetchall()
    for row in result:
        print(row)
finally:
    cursor.close()
    conn.close()
