"""
データベースルーター
Oracleデータベースは読み取り専用として使用し、すべての書き込みはdefault(PostgreSQL)に実行
"""


class DatabaseRouter:
    """
    読み取り専用Oracle接続用のデータベースルーター
    - 読み取り: Resultモデルはoracleデータベースから読み取り
    - 書き込み: すべてのモデルはdefaultデータベースに書き込み（Oracle書き込み禁止）
    """
    
    oracle_models = {'result'}
    
    def db_for_read(self, model, **hints):
        """読み取りアクセスの場合のデータベース選択"""
        if model._meta.app_label == 'production':
            if model._meta.model_name in self.oracle_models:
                return 'oracle'
        return 'default'
    
    def db_for_write(self, model, **hints):
        """書き込みアクセスの場合のデータベース選択 - Oracleへの書き込みは禁止"""
        # OracleDBへの書き込みは常に禁止し、defaultデータベースを使用
        return 'default'
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """マイグレーション実行許可の判定 - Oracleへのマイグレーションは禁止"""
        # Oracleデータベースへのマイグレーションは禁止
        if db == 'oracle':
            return False
        
        # defaultデータベースへのマイグレーションのみ許可
        return db == 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """リレーション許可の判定"""
        # 同じデータベース内でのリレーションは常に許可
        db_set = {'default', 'oracle'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        
        # Resultモデルと他のproductionモデル間のリレーションを許可
        if (hasattr(obj1, '_meta') and hasattr(obj2, '_meta') and
            obj1._meta.app_label == 'production' and obj2._meta.app_label == 'production'):
            return True
            
        return None