import snowflake.connector
from contextlib import contextmanager

@contextmanager
def snowflake_connection():
    """Snowflakeへの接続を管理するコンテキストマネージャー"""
    try:
        # 開発環境用の直接設定
        conn = snowflake.connector.connect(
            user='zhh001r_00_hime',
            password='Zhh001r_00_hime_99',
            account='rb73083.japan-east.azure',
            warehouse='HIME_01_XS',
            database='ILE01',
            schema='ZHH001',
            proxy_host='hime-proxy-srv.hime.melco.co.jp',
            proxy_port=9515
        )
        print("Snowflake connection successful!")  # 接続成功時のメッセージ
        yield conn
    except Exception as e:
        print(f"Snowflake connection error: {str(e)}")  # 接続エラー時のメッセージ
        raise
    finally:
        if 'conn' in locals():
            conn.close()


def test_connection():
    """接続テスト用の関数"""
    try:
        with snowflake_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT current_version()")
            version = cur.fetchone()[0]
            print(f"Successfully connected to Snowflake. Version: {version}")
            
            # 拠点一覧の取得テスト
            cur.execute("""
                SELECT STA_NO1, PLACE_NAME
                FROM HF1SDM01
                ORDER BY STA_NO1
            """)
            locations = cur.fetchall()
            print(f"Successfully retrieved {len(locations)} locations:")
            for loc in locations:
                print(f"  - {loc[0]}: {loc[1]}")
    except Exception as e:
        print(f"Error during connection test: {str(e)}")


def get_locations():
    """拠点一覧を取得（HF1SDM01）"""
    print('start get_locations')
    try:
        with snowflake_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT STA_NO1, PLACE_NAME
                FROM HF1SDM01
                ORDER BY STA_NO1
            """)
            locations = cur.fetchall()
            print(f"Retrieved {len(locations)} locations")  # デバッグ用出力
            return locations
    except Exception as e:
        print(f"Error fetching locations: {str(e)}")  # エラー出力
        return []


def get_lines_by_location(sta_no1):
    """指定拠点のライン一覧を取得（HF1SEM01）"""
    with snowflake_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT STA_NO1, STA_NO2, LINE_NAME
                FROM HF1SEM01
                WHERE STA_NO1 = %s
                ORDER BY STA_NO2
            """, (sta_no1,))
            return cur.fetchall()
        finally:
            cur.close()


def get_results(filters):
    """実績データを取得（HF1REM01）"""
    with snowflake_connection() as conn:
        cur = conn.cursor()
        try:
            # フィルター条件の構築
            conditions = []
            params = []
            
            if filters.get('sta_no1'):
                conditions.append("STA_NO1 = %s")
                params.append(filters['sta_no1'])
            
            if filters.get('sta_no2'):
                conditions.append("STA_NO2 = %s")
                params.append(filters['sta_no2'])
            
            if filters.get('timestamp_start'):
                conditions.append("MK_DATE >= %s")
                params.append(filters['timestamp_start'].strftime('%Y%m%d%H%M%S'))
            
            if filters.get('timestamp_end'):
                conditions.append("MK_DATE <= %s")
                params.append(filters['timestamp_end'].strftime('%Y%m%d%H%M%S'))
            
            if filters.get('machine'):
                conditions.append("STA_NO3 = %s")
                params.append(filters['machine'])
            
            if filters.get('serial_number'):
                conditions.append("M_SERIAL LIKE %s")
                params.append(f"%{filters['serial_number']}%")
            
            if filters.get('judgment'):
                conditions.append("OPEFIN_RESULT = %s")
                params.append('1' if filters['judgment'] == 'OK' else '2')
            
            # SQL文の構築
            sql = """
                SELECT 
                    MK_DATE,
                    STA_NO1,
                    STA_NO2,
                    STA_NO3,
                    PARTSNAME,
                    M_SERIAL,
                    OPEFIN_RESULT
                FROM HF1REM01
            """
            
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            
            sql += " ORDER BY MK_DATE DESC LIMIT 50"
            
            # クエリ実行
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()


def get_line_master(sta_no1):
    """
    指定された拠点コードのラインマスタ情報を取得
    """
    print(f'start get_line_master for {sta_no1}')  # デバッグ出力
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT STA_NO1, STA_NO2, LINE_NAME 
        FROM HF1SEM01 
        WHERE STA_NO1 = %s 
        ORDER BY STA_NO2
        """
        cursor.execute(query, (sta_no1,))
        results = cursor.fetchall()
        print(f'Retrieved {len(results)} lines')  # デバッグ出力
        
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f'Error in get_line_master: {str(e)}')  # エラー時のデバッグ出力
        return [] 