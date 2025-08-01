# ✅ アプリケーション要件 v10（完全・最終版 / 日本語）

---

## 1. 🎯 アプリケーション概要

* **名称（仮）**：生産計画・実績 見える化・分析アプリ
* **目的**：

  * 生産ラインの計画・実績を見える化
  * 機種別・ライン別に進捗状況を把握
  * ダッシュボードによるリアルタイム監視
  * 将来的な通知機能や生産性向上支援にも拡張可能

---

## 2. ⚙️ 開発方針

* **Django の Generic View（クラスベースビュー）を最大限活用**

  * `ListView`, `CreateView`, `UpdateView`, `DeleteView` などを可能な限り使用
* レイアウトは `base.html` に共通化
* グラフ表示には **Chart.js** を使用
* リアルタイム処理には **Daphne + Django Channels + WebSocket** を使用
* **再利用性・保守性・拡張性** を重視した設計方針
* **Snowflake連携**を基本とした設計

---

## 3. 🔐 認証・ユーザーアクセス制御

### ユーザー登録・認証

* `django-allauth` を用いたログイン／ログアウト／サインイン機能（メール不要）
* アカウント作成時：
  * Snowflakeに接続し、拠点を選択（HF1SDM01テーブル）
    * `STA_NO1`（拠点コード）
    * `PLACE_NAME`（拠点名）をプルダウンで表示
  * 選択した拠点コードをユーザー情報として保存（デフォルトnull許可）

### ライン権限設定

* 初回ログイン時（UserLineAccessが未設定の場合）：
  * Snowflakeに接続し、ライン選択画面を表示（HF1SEM01テーブル）
    * `STA_NO1`（拠点コード）でフィルタリング
    * `LINE_NAME`（ライン名）を一覧表示
    * 複数選択可能なチェックボックス形式
  * 選択したラインの情報をUserLineAccessに保存
    * `STA_NO2`（ラインコード）をline_idとして保存

### アクセス制御

* 各ユーザーがアクセスできる生産ラインを制限（UserLineAccess モデル）
* ログイン後、ダッシュボード表示用のライン選択画面に遷移
* ユーザーが最後に使用したラインを記憶し、次回以降の初期値とする（UserPreference モデル）

---

## 4. 🧠 モデル構成

| モデル名                     | 説明                              |
| ------------------------ | ------------------------------- |
| **User**                 | Django標準ユーザー + 拠点コード（STA_NO1）    |
| **Line**                 | 生産ライン（STA_NO2をIDとして使用）          |
| **UserLineAccess**       | ユーザーとラインのアクセス管理                 |
| **Machine**              | 設備（STA_NO3をIDとして使用）             |
| **Category**             | 機種カテゴリ（画面から追加・編集可）              |
| **Tag**                  | 機種タグ（複数可、画面から追加・編集可）            |
| **Part**                 | 機種（カテゴリ、タグ、目標PPH、サイクルタイム）       |
| **Plan**                 | 生産計画（日付、ライン、機種、順番、個数）           |
| **Result**               | 実績（計画、数量、タイムスタンプ、シリアル番号、判定）     |
| **WorkingDay**           | 稼働日管理（祝日や週末の指定）                 |
| **DashboardCardSetting** | ダッシュボードカードの表示／非表示設定（管理者用）       |
| **UserPreference**       | ユーザー設定（最後に選択したライン、テーマ）          |

---

## 5. 🕒 稼働時間・カレンダー設定

* 稼働時間設定：開始時刻（例：8:30）、朝礼時間、休憩時間（複数可）

  * 例：10:45–11:00、12:00–12:45、15:00–15:15、17:00–17:15
* 計画の時間帯は、朝礼・休憩・機種切替などの**ダウンタイムを除外**
* 実績は休憩中にも記録される場合がある
* `WorkingDay` モデルにより稼働日・非稼働日を管理

  * 土日・祝日は非稼働日として扱う（祝日は自動 or 手動対応）

---

## 6. 📝 生産計画入力ページ（GenericView利用）

* `CreateView` により生産計画を登録
* 入力内容：

  * 日付（デフォルト：今日）
  * ライン（ユーザーがアクセス可能なラインのみ表示）
  * 機械（選択したラインに紐づく機械のみ表示）
  * 機種（アクティブな機種のみ表示）
  * 開始時間・終了時間
  * 計画数量（1以上）
  * 順番（自動調整機能あり）
  * 備考

* 機種が未登録の場合、その場で登録可能（モーダルまたはリンク）：

  * 項目：機種名、品番、カテゴリ、タグ（複数）、目標PPH
  * サイクルタイムは `3600 ÷ 目標PPH` にて自動計算

---

## 7. 📈 実績一覧ページ（GenericView利用）

* `ListView` で実績一覧を表示
* データソース：Snowflakeデータベース（HF1REM01テーブル）
  * `MK_DATE`：タイムスタンプ（YYYYMMDDhhmmss形式）
  * `STA_NO1`：拠点コード（ユーザーの拠点でフィルタ）
  * `STA_NO2`：ラインコード（選択したラインでフィルタ）
  * `STA_NO3`：行程コード（machine）
  * `M_SERIAL`：シリアル番号
  * `OPEFIN_RESULT`：判定

* フィルタリング機能：

  * タイムスタンプ：範囲指定
  * 機械：選択
  * 機種：選択
  * シリアル番号：部分一致
  * 判定：選択（OK/NG）

* フィルタが未設定の場合は、最近3日間のデータを表示
* ページネーション（50件/ページ）

---

## 8. 📊 ダッシュボード（リアルタイム・Genericベース）

### アクセス

* ログイン後、アクセス可能なラインの一覧を表示
* ラインを選択してダッシュボードに遷移

### 表示項目

* 計画数、実績数、進捗率
* 進捗カード（目標・実績・進捗率）
* グラフ（Chart.js）：

  * 累積グラフ（線）
  * 時間別グラフ（1時間単位、機種ごとの積み上げ棒グラフ）

### ⏱ 時間あたりの計画自動算出

* 生産計画登録時に、

  * 稼働可能時間（朝の開始時刻から1時間刻み）をもとに
  * 朝礼・休憩・機種切替を除いた時間帯に計画数量を**時間ごとに自動分配**
  * 時間別グラフの「計画バー」に反映

### 🎨 進捗率によるカードの色分け

* 緑：100%以上、黄：80〜99%、赤：80%未満
* 閾値は `DashboardCardSetting` モデルで管理

---

## 9. 📅 週別・月別グラフページ

* 表示切替：タブまたはドロップダウンで「週別／月別」切替
* デフォルト：当日の属する週（週の開始は月曜日）

### 共通表示内容

* 累積実績（線グラフ）
* 日別・機種別の実績（積み上げ棒グラフ）
* 非稼働日はグレーまたは空欄で表示

### 週別

* 月曜～日曜（7日）を表示

### 月別

* 月初～月末の全日を表示

---

## 10. 🖼 フロントエンド設計

* `base.html` にて共通レイアウト定義
* ヘッダーに：

  * アプリ名、ログインユーザー名、各種リンク（ドロップダウンまたはアコーディオン）、ログアウトボタン
* 使用技術：**Bootstrap 5**

  * モダン・おしゃれ・Bootstrap感を抑えたスタイル
* **ダーク／ライトモード切替**に対応（`UserPreference` モデルで管理）
* CSSは共通化。個別スタイルは必要最小限とする

---

## 11. 🔄 リアルタイム更新（WebSocket）

* Daphne + Django Channels により ASGI 対応
* 実績登録時に：

  * ダッシュボードのグラフ／進捗カードが即時更新
* 将来的に通知（ポップアップ・サウンドなど）へ拡張可能な設計

---

## 12. ⚙️ 管理者機能

* Django 管理画面から以下を管理可能：

  * ライン、設備、機種、カテゴリ、タグ
  * 生産計画・実績
  * 稼働日（WorkingDay）と稼働時間設定
  * ダッシュボードのカード表示設定
* タグやカテゴリも、画面または管理画面から編集可能

---

## 13. 🗄 データベース構造

### Django データベース（SQLite/PostgreSQL）

#### User（ユーザー）
* `id`：主キー
* `username`：ユーザー名（一意）
* `password`：パスワード（ハッシュ化）
* `email`：メールアドレス（オプション）
* `is_active`：アクティブフラグ
* `is_staff`：管理者フラグ
* `is_superuser`：スーパーユーザーフラグ
* `date_joined`：登録日時
* `last_login`：最終ログイン日時
* `sta_no1`：拠点コード（外部キー、null許可）

#### Line（ライン）
* `id`：主キー（STA_NO2と同値）
* `name`：ライン名
* `description`：説明
* `is_active`：有効フラグ
* `created_at`：作成日時
* `updated_at`：更新日時

#### UserLineAccess（ユーザーライン権限）
* `id`：主キー
* `user_id`：ユーザーID（外部キー）
* `line_id`：ラインID（外部キー）
* `created_at`：作成日時

#### Machine（設備）
* `id`：主キー（STA_NO3と同値）
* `name`：設備名
* `line_id`：ラインID（外部キー）
* `description`：説明
* `is_active`：有効フラグ
* `is_production_active`：生産稼働フラグ
* `created_at`：作成日時
* `updated_at`：更新日時

#### Category（機種カテゴリ）
* `id`：主キー
* `name`：カテゴリ名（一意）
* `description`：説明
* `color`：表示色（HEX形式）
* `is_active`：有効フラグ
* `created_at`：作成日時
* `updated_at`：更新日時

#### Tag（機種タグ）
* `id`：主キー
* `name`：タグ名（一意）
* `description`：説明
* `color`：表示色（HEX形式）
* `is_active`：有効フラグ
* `created_at`：作成日時
* `updated_at`：更新日時

#### Part（機種）
* `id`：主キー
* `name`：機種名（一意）
* `part_number`：品番（一意、オプション）
* `category_id`：カテゴリID（外部キー）
* `target_pph`：目標PPH
* `cycle_time`：サイクルタイム（秒）
* `description`：説明
* `is_active`：有効フラグ
* `created_at`：作成日時
* `updated_at`：更新日時
* `tags`：タグ（多対多関連）

#### Plan（生産計画）
* `id`：主キー
* `date`：計画日
* `line_id`：ラインID（外部キー）
* `part_id`：機種ID（外部キー）
* `machine_id`：設備ID（外部キー）
* `start_time`：開始時間
* `end_time`：終了時間
* `planned_quantity`：計画数量
* `sequence`：順番
* `notes`：備考
* `created_at`：作成日時
* `updated_at`：更新日時

#### Result（実績）
* `id`：主キー
* `plan_id`：計画ID（外部キー、null許可）
* `quantity`：数量
* `timestamp`：タイムスタンプ
* `serial_number`：シリアル番号
* `judgment`：判定（OK/NG）
* `notes`：備考
* `created_at`：作成日時

#### WorkingDay（稼働日）
* `id`：主キー
* `date`：日付（一意）
* `is_working`：稼働フラグ
* `is_holiday`：祝日フラグ
* `holiday_name`：祝日名
* `start_time`：開始時間
* `end_time`：終了時間
* `break_minutes`：休憩時間（分）
* `description`：説明
* `created_at`：作成日時
* `updated_at`：更新日時

#### DashboardCardSetting（ダッシュボード設定）
* `id`：主キー
* `name`：カード名（一意）
* `is_visible`：表示フラグ
* `order`：表示順
* `alert_threshold_yellow`：黄色アラート閾値（%）
* `alert_threshold_red`：赤色アラート閾値（%）
* `created_at`：作成日時
* `updated_at`：更新日時

#### UserPreference（ユーザー設定）
* `id`：主キー
* `user_id`：ユーザーID（外部キー）
* `last_selected_line_id`：最後に選択したラインID（外部キー）
* `theme`：テーマ（light/dark）
* `created_at`：作成日時
* `updated_at`：更新日時

### Snowflake データベース

#### HF1SDM01（拠点コードマスター）
* `STA_NO1`：拠点コード（主キー）
  * 型：VARCHAR
  * 説明：拠点を一意に識別するコード
* `PLACE_NAME`：拠点名
  * 型：VARCHAR
  * 説明：拠点の表示名
* その他の管理項目
  * 作成日時、更新日時など

#### HF1SEM01（ラインコードマスター）
* `STA_NO1`：拠点コード（複合主キー）
  * 型：VARCHAR
  * 説明：拠点を識別するコード
* `STA_NO2`：ラインコード（複合主キー）
  * 型：VARCHAR
  * 説明：ラインを一意に識別するコード
* `LINE_NAME`：ライン名
  * 型：VARCHAR
  * 説明：ラインの表示名
* その他の管理項目
  * 作成日時、更新日時など

#### HF1REM01（実績データ）
* `MK_DATE`：タイムスタンプ
  * 型：VARCHAR(14)
  * 形式：YYYYMMDDhhmmss
  * 説明：実績が記録された日時
* `STA_NO1`：拠点コード
  * 型：VARCHAR
  * 説明：実績が記録された拠点
* `STA_NO2`：ラインコード
  * 型：VARCHAR
  * 説明：実績が記録されたライン
* `STA_NO3`：行程コード
  * 型：VARCHAR
  * 説明：実績が記録された工程
* `PARTSNAME`：品名
  * 型：VARCHAR
  * 説明：製品の品名
* `M_SERIAL`：シリアル番号
  * 型：VARCHAR
  * 説明：製品のシリアル番号
* `OPEFIN_RESULT`：判定
  * 型：VARCHAR(1)
  * 値：1=OK, 2=NG
  * 説明：検査結果
* その他の管理項目
  * 作成者、作成日時、更新者、更新日時など

### データ連携

#### Django → Snowflake
* 実績データの参照のみ
* 書き込みは行わない（読み取り専用）

#### Snowflake → Django
* マスターデータの同期
  * 拠点情報（HF1SDM01）
  * ライン情報（HF1SEM01）
* 実績データの取得（HF1REM01）
  * フィルター条件に基づいて必要なデータのみ取得
  * パフォーマンスを考慮した適切なインデックス利用

---

## ✅ 機能チェックリスト

| 機能                     | 対応状況               |
| ---------------------- | ------------------ |
| Django Generic Viewの活用 | ✅ 全CRUDに使用         |
| 認証（ライン制限）              | ✅ django-allauth使用 |
| Snowflake連携            | ✅ マスター・トランザクション   |
| 機種／設備／ライン管理            | ✅                  |
| 計画登録（モーダルで機種追加）        | ✅                  |
| 実績一覧（詳細フィルタ付き）         | ✅                  |
| ダッシュボード（グラフ・カード）       | ✅                  |
| 時間当たりの計画値自動算出          | ✅                  |
| 週別・月別グラフ表示             | ✅                  |
| ダーク／ライトモード切替           | ✅                  |
| WebSocketリアルタイム更新      | ✅                  |
| 管理画面での完全制御             | ✅                  |

---

これが「**アプリケーション要件 v10（完全版・日本語）**」です。
Snowflake連携の詳細と、ユーザー管理の仕様を追加・更新しました。

## 14. 📱 画面構成

### 認証関連画面

#### ログイン画面
* パス：`/accounts/login/`
* 表示項目：
  * ユーザー名入力フィールド
  * パスワード入力フィールド
  * ログインボタン
  * アカウント作成リンク
* 機能：
  * ユーザー認証
  * 認証後、ライン選択画面へ遷移

#### アカウント作成画面
* パス：`/accounts/signup/`
* 表示項目：
  * ユーザー名入力フィールド
  * パスワード入力フィールド
  * パスワード（確認）入力フィールド
  * 拠点選択プルダウン（HF1SDM01.PLACE_NAME）
* 機能：
  * アカウント作成
  * 拠点コード（STA_NO1）の紐付け
  * 作成後、ライン選択画面へ遷移

### メイン画面

#### ライン選択画面
* パス：`/line/select/`
* 表示項目：
  * アクセス可能なライン一覧
    * ライン名（HF1SEM01.LINE_NAME）
    * ライン説明
    * 最終アクセス日時
  * ライン追加ボタン（初回ログイン時のみ）
* 機能：
  * ライン選択によるダッシュボードへの遷移
  * 最後に選択したラインの記憶

#### ライン追加画面
* パス：`/line/add/`
* 表示項目：
  * ユーザーの拠点のライン一覧（HF1SEM01）
    * チェックボックス
    * ライン名（LINE_NAME）
    * ライン説明
  * 保存ボタン
* 機能：
  * 複数ラインの選択
  * UserLineAccessへの保存

#### ダッシュボード
* パス：`/dashboard/<line_id>/`
* 表示項目：
  * ライン情報ヘッダー
    * ライン名
    * 現在の日付・時刻
  * 進捗カード
    * 計画数
    * 実績数
    * 進捗率
    * 目標達成予測
  * グラフエリア
    * 累積グラフ（計画vs実績）
    * 時間別生産数グラフ
  * 最新実績リスト
    * タイムスタンプ
    * 機種名
    * シリアル番号
    * 判定結果
* 機能：
  * リアルタイム更新
  * 進捗率による色分け表示
  * グラフの自動更新

#### 生産計画一覧
* パス：`/plan/<line_id>/`
* 表示項目：
  * 日付選択カレンダー
  * 計画一覧テーブル
    * 順番
    * 開始-終了時間
    * 機種名
    * 計画数量
    * 実績数量
    * 進捗率
    * 操作ボタン（編集・削除）
  * 新規計画作成ボタン
* 機能：
  * 日付による計画表示
  * 計画の追加・編集・削除
  * 実績との紐付け表示

#### 生産計画作成/編集
* パス：`/plan/<line_id>/create/` または `/plan/<line_id>/edit/<plan_id>/`
* 表示項目：
  * 日付選択
  * ライン（固定表示）
  * 機械選択
  * 機種選択
  * 開始時間
  * 終了時間
  * 計画数量
  * 順番
  * 備考
* 機能：
  * 計画の新規作成/編集
  * 機種未登録時の登録機能
  * 時間重複チェック
  * 順番の自動調整

#### 機種登録/編集
* パス：`/part/create/` または `/part/edit/<part_id>/`
* 表示項目：
  * 機種名
  * 品番
  * カテゴリ選択
  * タグ選択（複数可）
  * 目標PPH
  * サイクルタイム（自動計算）
  * 説明
* 機能：
  * 機種の新規作成/編集
  * サイクルタイムの自動計算
  * カテゴリ・タグの動的追加

#### 実績一覧
* パス：`/result/<line_id>/`
* 表示項目：
  * フィルター条件
    * 期間（開始-終了）
    * 機械
    * 機種
    * シリアル番号
    * 判定
  * 実績一覧テーブル
    * タイムスタンプ
    * 機械名
    * 機種名
    * シリアル番号
    * 判定結果
    * 備考
  * ページネーション
* 機能：
  * Snowflakeからのデータ取得
  * 条件によるフィルタリング
  * CSV出力

#### 週別/月別グラフ
* パス：`/graph/<line_id>/weekly/` または `/graph/<line_id>/monthly/`
* 表示項目：
  * 期間選択
    * 週選択（月曜-日曜）
    * 月選択（1日-末日）
  * 表示切替タブ
    * 週別
    * 月別
  * グラフエリア
    * 累積実績グラフ
    * 日別・機種別実績グラフ
  * 集計情報
    * 期間合計
    * 日平均
    * 最大/最小
* 機能：
  * 期間による表示切替
  * グラフ形式の切替
  * データの集計表示

### 管理画面

#### システム管理
* パス：`/admin/`
* 管理項目：
  * ユーザー管理
  * ライン管理
  * 機械管理
  * カテゴリ管理
  * タグ管理
  * 機種管理
  * 計画管理
  * 実績管理
  * 稼働日管理
  * ダッシュボード設定
* 機能：
  * マスターデータのCRUD
  * データ一括登録
  * ログ確認

#### ユーザー設定
* パス：`/settings/`
* 表示項目：
  * テーマ設定（ライト/ダーク）
  * 表示言語
  * 通知設定
  * パスワード変更
* 機能：
  * 設定の保存
  * 即時反映

