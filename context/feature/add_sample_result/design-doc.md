# 生産実績データサンプル生成 設計方針書

## 📋 概要

生産実績データのサンプルを自動生成するDjangoカスタムコマンドの設計方針を定義します。このコマンドは、既存の生産計画データと計画PPHを基に、現実的な生産実績データを生成します。

## 🔍 要件の分析

要件定義書から抽出した主要な実装ポイント：

1. **データ生成の時系列制御**
   - 生産開始から終了までの時間管理
   - 休憩時間による生産停止
   - 機種切替時のダウンタイム
   - 翌日8:30までの制限

2. **生産数量の制御**
   - 計画数量の100-105%の達成
   - 0-10%の不良品率
   - サイクルタイムの100-110%のばらつき

3. **データの整合性**
   - 同一ライン内での設備間データ同期
   - 既存データの削除と新規生成
   - タイムゾーンの一貫性（JST）

## 🛠 実装方針

### アーキテクチャ選択

Djangoのカスタムコマンドとして実装し、以下の構造を採用します：

1. **コマンドクラス**: `BaseCommand`を継承
2. **データ生成サービス**: 実績データ生成ロジックを分離
3. **ファクトリークラス**: テストデータ生成の再利用性を確保

### コンポーネント設計

1. **CommandHandler**
   - コマンドライン引数の処理
   - 全体の処理フロー制御
   - 進捗表示

2. **ResultDataGenerator**
   - 生産実績データの生成ロジック
   - 時間管理と数量制御
   - 不良品生成

3. **TimeManager**
   - 生産時間の管理
   - 休憩時間の制御
   - 機種切替時間の制御

4. **DataValidator**
   - 生成データの妥当性検証
   - 制約条件のチェック

### データフロー

1. コマンド実行
2. 対象期間・ラインの計画データ取得
3. 既存実績データの削除
4. 時系列に沿った実績データ生成
5. バッチ処理による一括保存

## 🔄 実装方法の選択肢と決定

### 選択肢1: 単一トランザクションでの一括処理

- **利点**:
  - データの整合性が保証される
  - 実装がシンプル
- **欠点**:
  - 大量データ処理時のメモリ使用量
  - ロールバック時のオーバーヘッド

### 選択肢2: バッチ処理による段階的生成

- **利点**:
  - メモリ効率が良い
  - 部分的な失敗時の影響が限定的
- **欠点**:
  - 実装が複雑
  - トランザクション境界の管理が必要

### 決定: バッチ処理による段階的生成

選択理由：
1. 長期間のデータ生成時のメモリ効率を重視
2. 生成処理の途中経過が確認可能
3. エラー発生時の部分的なリカバリが容易

## 📊 技術的制約と考慮事項

1. **メモリ使用量**
   - バッチサイズの初期値: 1000件
   - メモリ使用量のモニタリング
   - 必要に応じてバッチサイズの動的調整

2. **パフォーマンス**
   - `bulk_create`の活用
   - クエリの最適化
   - インデックスの効果的な利用

3. **データ整合性**
   - 日付境界の正確な処理
   - タイムゾーン変換の一貫性
   - 休憩時間と機種切替の正確な反映

4. **エラーハンドリング**
   - 途中失敗時のロールバック戦略
   - エラーログの詳細な記録
   - リトライ機構の実装

5. **進捗表示**
   - 処理中の詳細情報表示
     ```
     [2024-03-20] ライン1の処理中...
     - 計画数: 1000個
     - 現在の生産数: 800個 (80%)
     - 不良品数: 50個 (6.25%)
     - 現在処理中の機種: Part-A
     - 次の機種: Part-B
     - 予想残り時間: 30分
     ```
   - エラー発生時の詳細表示
     ```
     [エラー] ライン1の処理中にエラーが発生
     - 発生時刻: 2024-03-20 14:30:00
     - エラー内容: [エラーメッセージ]
     - 処理済み件数: 800件
     - 最後に処理した機種: Part-A
     ```

6. **データ検証**
   - 要件適合性の確認
     - 生産数が計画の100-105%の範囲内
     - 不良品率が0-10%の範囲内
     - サイクルタイムが基準の100-110%の範囲内
   - 時間的整合性の確認
     - 生産終了時刻が翌日8:30以前
     - 休憩時間中の生産がないこと
     - 機種切替時間の確保
   - 設備間データの同期確認
     - 同一ライン内の全設備で同一データ

## ❓ 解決すべき技術的課題

1. **バッチサイズの最適化**
   - 初期値1000件からの自動調整メカニズム
   - メモリ使用量の監視方法

2. **進捗表示の更新頻度**
   - リアルタイム更新と処理効率のバランス
   - 大量データ処理時のパフォーマンス影響

3. **データ検証のタイミング**
   - バッチ処理中の検証タイミング
   - エラー検出時の処理継続判断

## 📝 実装の具体的な流れ

```python
# コマンドの基本構造
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--line', type=int, help='ライン番号')
        parser.add_argument('--date', type=str, help='開始日 (YYYY-MM-DD)')
        parser.add_argument('--days', type=int, help='生成日数')

    def handle(self, *args, **options):
        self.generator = ResultDataGenerator()
        self.time_manager = TimeManager()
        self.validator = DataValidator()
        
        try:
            # 1. パラメータ検証
            self.validate_parameters(options)
            
            # 2. 既存データ削除
            self.delete_existing_data(options['date'], options['days'])
            
            # 3. 生成処理実行
            for day in range(options['days']):
                current_date = self.calculate_date(options['date'], day)
                self.process_single_day(current_date, options['line'])
                
        except Exception as e:
            self.handle_error(e)

    def process_single_day(self, date, line):
        self.stdout.write(f"[{date}] ライン{line}の処理開始...")
        
        # 進捗表示用の状態管理
        state = {
            'planned_quantity': 0,
            'current_quantity': 0,
            'defect_quantity': 0,
            'current_part': None,
            'next_part': None,
        }
        
        # 生産データ生成（進捗状態を更新）
        results = self.generator.generate_for_date(date, line, state)
        
        # データ検証
        self.validator.validate_results(results)
        
        # 結果の保存
        self.save_results(results)

# データ生成サービス
class ResultDataGenerator:
    BATCH_SIZE = 1000  # 初期バッチサイズ

    def generate_for_date(self, date, line, state):
        # 実装詳細
        pass

# 時間管理
class TimeManager:
    def is_break_time(self, time):
        # 休憩時間チェック
        pass

    def calculate_next_production_time(self, current_time):
        # 次の生産時刻計算
        pass

# データ検証
class DataValidator:
    def validate_results(self, results):
        self.validate_production_quantity(results)
        self.validate_defect_rate(results)
        self.validate_cycle_time(results)
        self.validate_time_constraints(results)
        self.validate_equipment_sync(results)
``` 