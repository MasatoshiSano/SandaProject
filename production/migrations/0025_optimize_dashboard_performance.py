# Generated manually for dashboard performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0024_dashboardcardsetting_card_type_and_more'),
    ]

    operations = [
        # PostgreSQL（デフォルトDB）のインデックス最適化
        migrations.RunSQL(
            """
            -- 計画テーブルのインデックス
            CREATE INDEX IF NOT EXISTS idx_plan_line_date ON production_plan(line_id, date);
            CREATE INDEX IF NOT EXISTS idx_plan_line_date_sequence ON production_plan(line_id, date, sequence);
            
            -- 機種テーブルのインデックス
            CREATE INDEX IF NOT EXISTS idx_part_name ON production_part(name);
            
            -- 設備テーブルのインデックス
            CREATE INDEX IF NOT EXISTS idx_machine_line_active_count ON production_machine(line_id, is_active, is_count_target);
            
            -- 段替えダウンタイムテーブルのインデックス
            CREATE INDEX IF NOT EXISTS idx_partchange_line_from_to ON production_partchangedowntime(line_id, from_part_id, to_part_id);
            
            -- 計画時間別生産数テーブルのインデックス
            CREATE INDEX IF NOT EXISTS idx_planned_hourly_line_date_hour ON production_plannedhourlyproduction(line_id, date, hour);
            
            -- 予測テーブルのインデックス
            CREATE INDEX IF NOT EXISTS idx_forecast_line_date ON production_productionforecast(line_id, target_date);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_plan_line_date;
            DROP INDEX IF EXISTS idx_plan_line_date_sequence;
            DROP INDEX IF EXISTS idx_part_name;
            DROP INDEX IF EXISTS idx_machine_line_active_count;
            DROP INDEX IF EXISTS idx_partchange_line_from_to;
            DROP INDEX IF EXISTS idx_planned_hourly_line_date_hour;
            DROP INDEX IF EXISTS idx_forecast_line_date;
            """
        ),
        
        # Resultテーブル（Oracle）のインデックス最適化は手動で実行する必要があります
        # 以下のSQLを本番環境のOracleで実行してください：
        # CREATE INDEX idx_hf1rem01_line_part_time ON HF1REM01(STA_NO2, partsname, MK_DATE);
        # CREATE INDEX idx_hf1rem01_line_judgment_time ON HF1REM01(STA_NO2, OPEFIN_RESULT, MK_DATE);
        # CREATE INDEX idx_hf1rem01_composite_opt ON HF1REM01(STA_NO1, STA_NO2, OPEFIN_RESULT, partsname, MK_DATE);
        # CREATE INDEX idx_hf1rem01_machine_time ON HF1REM01(STA_NO3, MK_DATE);
        
        # 空のSQL操作（Oracleインデックスは手動作成のため）
        migrations.RunSQL(
            "SELECT 1;",  # ダミーSQL
            reverse_sql="SELECT 1;"
        ),
        
        # DashboardCardSettingのcard_typeフィールドの一意制約は既に存在するためスキップ
    ]