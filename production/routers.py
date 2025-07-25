"""
データベースルーター
Resultモデルのみoracleデータベースを使用し、その他のモデルはdefault(PostgreSQL)を使用
"""


class DatabaseRouter:
    """
    Resultモデル用のデータベースルーター
    """
    
    oracle_models = {'result'}
    
    def db_for_read(self, model, **hints):
        """読み取りアクセスの場合のデータベース選択"""
        if model._meta.app_label == 'production':
            if model._meta.model_name in self.oracle_models:
                return 'oracle'
        return 'default'
    
    def db_for_write(self, model, **hints):
        """書き込みアクセスの場合のデータベース選択"""
        if model._meta.app_label == 'production':
            if model._meta.model_name in self.oracle_models:
                return 'oracle'
        return 'default'
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """マイグレーション実行許可の判定"""
        if app_label == 'production':
            if model_name in self.oracle_models:
                return db == 'oracle'
            else:
                return db == 'default'
        
        # その他のアプリケーションは default のみ
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