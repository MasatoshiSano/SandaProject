# SandaProject Docker環境

このプロジェクトはDocker Composeを使用してPostgreSQL、Redis、Nginx、DaphneでのDjango環境を構築しています。

## 構成

- **Django**: Python 3.10 + Daphne (ASGI サーバー)
- **データベース**: PostgreSQL 15
- **キャッシュ/セッション**: Redis 7
- **Webサーバー**: Nginx (リバースプロキシ)
- **チャンネル**: Django Channels + Redis

## 起動方法

### 1. 環境設定

`.env`ファイルを確認・編集してください：

```bash
# Django設定
SECRET_KEY=django-insecure-docker-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,web,nginx

# PostgreSQL設定
POSTGRES_DB=sandaproject
POSTGRES_USER=sandauser
POSTGRES_PASSWORD=sandapass
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis設定
REDIS_HOST=redis
REDIS_PORT=6379
```

### 2. Docker Composeで起動

```bash
# すべてのサービスを起動
docker-compose up -d

# ログを確認
docker-compose logs -f

# 特定のサービスのログを確認
docker-compose logs -f web
```

### 3. アクセス

- **アプリケーション**: http://localhost (Nginx経由)
- **直接アクセス**: http://localhost:8000 (Daphne直接)
- **管理画面**: http://localhost/admin/
  - ユーザー名: `admin`
  - パスワード: `admin123`

## 管理コマンド

### データベース操作

```bash
# マイグレーション実行
docker-compose exec web python manage.py migrate --settings=config.settings_docker

# スーパーユーザー作成
docker-compose exec web python manage.py createsuperuser --settings=config.settings_docker

# シェル起動
docker-compose exec web python manage.py shell --settings=config.settings_docker
```

### サンプルデータ作成

```bash
# サンプルデータ作成
docker-compose exec web python manage.py create_sample_data --settings=config.settings_docker

# 実績データ作成
docker-compose exec web python manage.py seed_result_data --days 3 --settings=config.settings_docker
```

### サービス管理

```bash
# サービス停止
docker-compose down

# ボリュームも削除して完全クリーンアップ
docker-compose down -v

# 特定のサービスを再起動
docker-compose restart web

# サービスをスケール
docker-compose up -d --scale worker=2
```

## ディレクトリ構成

```
.
├── docker-compose.yml          # Docker Compose設定
├── Dockerfile                  # Djangoアプリ用Dockerfile
├── .env                       # 環境変数
├── .dockerignore              # Docker除外ファイル
├── requirements.txt           # Python依存関係
├── scripts/
│   └── entrypoint.sh         # コンテナ起動スクリプト
├── nginx/
│   ├── nginx.conf            # Nginx基本設定
│   └── default.conf          # サイト設定
└── config/
    ├── settings_docker.py    # Docker環境用Django設定
    └── ...
```

## 本番環境向け設定

本番環境では以下の変更を行ってください：

1. **セキュリティ設定**:
   ```bash
   # .envファイル
   SECRET_KEY=強力なランダムキー
   DEBUG=False
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   ```

2. **SSL/TLS設定**:
   - `nginx/ssl/`にSSL証明書を配置
   - `nginx/default.conf`でHTTPS設定を有効化

3. **データベース**:
   - 強力なパスワードに変更
   - バックアップ設定

## トラブルシューティング

### よくある問題

1. **ポート競合**:
   ```bash
   # 使用中のポートを確認
   docker-compose ps
   netstat -tulpn | grep :80
   ```

2. **データベース接続エラー**:
   ```bash
   # データベースコンテナの状態確認
   docker-compose logs db
   docker-compose exec db pg_isready -U sandauser -d sandaproject
   ```

3. **静的ファイルが表示されない**:
   ```bash
   # 静的ファイル収集
   docker-compose exec web python manage.py collectstatic --noinput --settings=config.settings_docker
   ```

### ログ確認

```bash
# 全サービスのログ
docker-compose logs

# リアルタイムログ
docker-compose logs -f

# エラーのみ表示
docker-compose logs | grep ERROR
```

## 開発時の注意事項

- ファイル変更は自動的にコンテナに反映されます（ボリュームマウント）
- 新しいPythonパッケージを追加した場合は、コンテナを再ビルドしてください：
  ```bash
  docker-compose build web
  docker-compose up -d web
  ```