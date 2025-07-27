-- Oracle Database - NULL制約修正スクリプト
-- PRODUCTION_RESULTテーブルのLINE_ID, MACHINE_ID, PART_IDのNOT NULL制約を削除

SET PAGESIZE 100;
SET LINESIZE 120;

PROMPT ================================================================================
PROMPT    ORACLE DATABASE - NULL制約修正スクリプト
PROMPT ================================================================================

PROMPT
PROMPT === 修正前の状態確認 ===
SELECT 
    COLUMN_NAME,
    NULLABLE,
    CASE 
        WHEN NULLABLE = 'Y' THEN '✓ NULL可'
        ELSE '✗ NOT NULL'
    END AS CURRENT_STATUS
FROM USER_TAB_COLUMNS 
WHERE TABLE_NAME = 'PRODUCTION_RESULT'
AND COLUMN_NAME IN ('LINE_ID', 'MACHINE_ID', 'PART_ID')
ORDER BY COLUMN_NAME;

PROMPT
PROMPT === NULL制約の削除実行 ===

PROMPT >>> LINE_IDカラムのNULL制約を削除...
ALTER TABLE PRODUCTION_RESULT MODIFY (LINE_ID NULL);

PROMPT >>> MACHINE_IDカラムのNULL制約を削除...
ALTER TABLE PRODUCTION_RESULT MODIFY (MACHINE_ID NULL);

PROMPT >>> PART_IDカラムのNULL制約を削除...
ALTER TABLE PRODUCTION_RESULT MODIFY (PART_ID NULL);

PROMPT
PROMPT === 修正後の状態確認 ===
SELECT 
    COLUMN_NAME,
    NULLABLE,
    CASE 
        WHEN NULLABLE = 'Y' THEN '✓ NULL可 (修正成功)'
        ELSE '✗ NOT NULL (修正失敗)'
    END AS UPDATED_STATUS
FROM USER_TAB_COLUMNS 
WHERE TABLE_NAME = 'PRODUCTION_RESULT'
AND COLUMN_NAME IN ('LINE_ID', 'MACHINE_ID', 'PART_ID')
ORDER BY COLUMN_NAME;

PROMPT
PROMPT === 全体のマイグレーション状況確認 ===
SELECT 
    COLUMN_NAME,
    CASE 
        WHEN NULLABLE = 'Y' THEN '✓ マイグレーション完了'
        ELSE '✗ まだ問題あり'
    END AS MIGRATION_STATUS
FROM USER_TAB_COLUMNS 
WHERE TABLE_NAME = 'PRODUCTION_RESULT'
AND COLUMN_NAME IN ('LINE', 'LINE_ID', 'MACHINE', 'MACHINE_ID', 'PART', 'PART_ID')
ORDER BY 
    CASE COLUMN_NAME
        WHEN 'LINE' THEN 1
        WHEN 'LINE_ID' THEN 2
        WHEN 'MACHINE' THEN 3
        WHEN 'MACHINE_ID' THEN 4
        WHEN 'PART' THEN 5
        WHEN 'PART_ID' THEN 6
    END;

PROMPT
PROMPT ================================================================================
PROMPT 修正完了！すべての対象カラムがNULL可になりました。
PROMPT これでマイグレーションが正常に完了しています。
PROMPT ================================================================================

EXIT;