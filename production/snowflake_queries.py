from datetime import datetime
from .connect_snowflake import get_snowflake_connection

class ResultQuery:
    @staticmethod
    def get_results(filters=None):
        """
        Snowflakeから実績データを取得
        
        Args:
            filters (dict): フィルター条件
        Returns:
            list: 実績データのリスト
        """
        query = """
            SELECT 
                'SAND' as sta_no1,
                sta_no2 as line,
                sta_no3 as machine,
                partsname as part,
                mk_date as timestamp,
                m_serial as serial_number,
                CASE 
                    WHEN opefin_result = 1 THEN 'OK'
                    WHEN opefin_result = 2 THEN 'NG'
                    ELSE 'Unknown'
                END as judgment
            FROM HF1REM01
            WHERE 1=1
        """
        
        params = {}
        
        if filters:
            if filters.get('line'):
                query += " AND sta_no2 = %(line)s"
                params['line'] = filters['line']
            
            if filters.get('machine'):
                query += " AND sta_no3 = %(machine)s"
                params['machine'] = filters['machine']
            
            if filters.get('part'):
                query += " AND partsname = %(part)s"
                params['part'] = filters['part']
            
            if filters.get('serial_number'):
                query += " AND m_serial LIKE %(serial_number)s"
                params['serial_number'] = f"%{filters['serial_number']}%"
            
            if filters.get('judgment'):
                query += " AND opefin_result = %(judgment)s"
                params['judgment'] = 1 if filters['judgment'].upper() == 'OK' else 2
            
            if filters.get('timestamp_start'):
                query += " AND mk_date >= %(timestamp_start)s"
                params['timestamp_start'] = filters['timestamp_start'].strftime('%Y%m%d%H%M%S')
            
            if filters.get('timestamp_end'):
                query += " AND mk_date <= %(timestamp_end)s"
                params['timestamp_end'] = filters['timestamp_end'].strftime('%Y%m%d%H%M%S')
        
        query += " ORDER BY mk_date DESC"
        
        with get_snowflake_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # 列名を取得
            columns = [desc[0].lower() for desc in cursor.description]
            
            # 結果を辞書のリストに変換
            results_list = []
            for row in results:
                result_dict = dict(zip(columns, row))
                # mk_dateをdatetimeに変換
                if result_dict.get('timestamp'):
                    result_dict['timestamp'] = datetime.strptime(
                        str(result_dict['timestamp']), 
                        '%Y%m%d%H%M%S'
                    )
                results_list.append(result_dict)
            
            return results_list 