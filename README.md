# SandaProject - 生産管理システム

Django製の生産管理システムです。生産ライン別の計画・実績管理、リアルタイムダッシュボード、進捗監視機能を提供します。

## 主な機能

### 🏭 生産管理機能
- **生産計画管理**: 機種別・ライン別の生産計画作成と管理
- **実績管理**: 実際の生産実績記録と分析
- **進捗監視**: リアルタイムでの生産進捗確認
- **PPH計算**: 計画時間当たり生産数の自動計算

### 📊 ダッシュボード機能
- **リアルタイム更新**: WebSocketによる自動データ更新
- **グラフ表示**: 週次・月次のパフォーマンス分析
- **アラート機能**: 生産遅延や異常の通知

### 👥 ユーザー管理
- **ライン別アクセス制御**: ユーザーごとのライン権限管理
- **認証システム**: Django Allauthによる認証
- **ロールベース権限**: 管理者・オペレーター等の権限制御

### 🔗 外部連携
- **Snowflake連携**: データウェアハウスとの連携
- **Oracle Database**: 生産データベースとの統合
- **API提供**: RESTful APIによるデータ連携

## 技術スタック

### バックエンド
- **Django 4.2.7**: Webフレームワーク
- **Django Channels**: WebSocket・リアルタイム通信
- **Redis**: セッション管理・メッセージブローカー
- **Daphne**: ASGIサーバー

### データベース
- **SQLite**: 開発環境
- **MySQL/Oracle**: 本番環境対応
- **Snowflake**: データウェアハウス

### フロントエンド
- **HTML/CSS/JavaScript**: レスポンシブUI
- **WebSocket**: リアルタイム更新
- **Chart.js**: グラフ表示

### インフラ
- **Docker**: コンテナ化
- **Nginx**: Webサーバー・リバースプロキシ
- **Gunicorn**: WSGIサーバー

## システム要件

- Python 3.8+
- Django 4.2.7
- Redis Server
- 対応データベース: SQLite, MySQL, Oracle

## セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/MasatoshiSano/SandaProject.git
cd SandaProject
```

### 2. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 3. データベースのセットアップ
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. 管理者ユーザーの作成
```bash
python manage.py createsuperuser
```

### 5. 開発サーバーの起動
```bash
# ASGIサーバー（推奨）
daphne -p 8000 config.asgi:application

# または通常のDjangoサーバー
python manage.py runserver
```

## Docker環境での実行

### 開発環境
```bash
docker-compose up -d
```

### 本番環境
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 主要なコマンド

### データ管理
```bash
# サンプルデータの作成
python manage.py create_sample_data

# 実績データのシード
python manage.py seed_result_data

# PPH計算の実行
python manage.py calculate_planned_pph
```

### データベース確認
```bash
# データベース接続確認
python check_db.py

# 実績データ確認
python check_results.py
```

## API エンドポイント

### 認証
- `POST /accounts/login/` - ログイン
- `POST /accounts/logout/` - ログアウト

### 生産管理
- `GET /production/dashboard/<line_id>/<date>/` - ダッシュボード
- `GET /production/plan/<line_id>/<date>/` - 生産計画
- `GET /production/result/<line_id>/` - 生産実績
- `GET /production/api/weekly-graph/<line_id>/` - 週次グラフデータ
- `GET /production/api/monthly-graph/<line_id>/` - 月次グラフデータ

## プロジェクト構成

```
SandaProject/
├── config/                 # Django設定
├── production/             # メインアプリケーション
│   ├── models.py          # データモデル
│   ├── views.py           # ビューロジック
│   ├── urls.py            # URLルーティング
│   ├── consumers.py       # WebSocketコンシューマー
│   └── management/        # 管理コマンド
├── templates/             # HTMLテンプレート
├── static/                # 静的ファイル
├── scripts/               # デプロイスクリプト
└── oracle_*.py           # Oracleデータベース関連ツール
```

## 主要なモデル

- **Line**: 生産ライン
- **Machine**: 機械・設備
- **Part**: 製品・部品
- **Plan**: 生産計画
- **Result**: 生産実績
- **UserLineAccess**: ユーザーアクセス権限

## デバッグツール

プロジェクトには以下のデバッグ・調査ツールが含まれています：

- `debug_oracle_schema.py` - Oracleスキーマ調査
- `simple_oracle_inspector.py` - Oracle接続テスト
- `test_color_generation.py` - 色生成テスト
- `oracle_schema_check*.sql` - スキーマ確認SQL

## 設定ファイル

### 環境変数
主要な設定は環境変数で管理：
- `SECRET_KEY`: Django秘密鍵
- `DEBUG`: デバッグモード
- `DATABASE_URL`: データベース接続URL
- `REDIS_URL`: Redis接続URL

### 設定ファイル
- `config/settings.py`: 基本設定
- `config/settings_docker.py`: Docker環境用設定

## ライセンス

このプロジェクトは私的利用のため、ライセンスは設定されていません。

## 貢献

このプロジェクトは現在プライベート開発中です。

## サポート

問題や質問がある場合は、GitHubのIssuesでお知らせください。

---

**開発者**: Masatoshi Sano  
**最終更新**: 2025年7月