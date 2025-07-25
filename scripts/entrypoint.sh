#!/bin/bash
set -e

# データベースの準備ができるまで待機
echo "Waiting for postgres..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done
echo "PostgreSQL started"

# Redisの準備ができるまで待機
echo "Waiting for redis..."
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  sleep 0.1
done
echo "Redis started"

# データベースマイグレーション
echo "Running database migrations..."
python manage.py migrate --settings=config.settings_docker

# 静的ファイルの収集
echo "Collecting static files..."
python manage.py collectstatic --noinput --settings=config.settings_docker

# スーパーユーザーが存在しない場合は作成
echo "Creating superuser if not exists..."
python manage.py shell --settings=config.settings_docker << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
EOF

# 引数に基づいてコマンドを実行
if [ "$1" = "web" ]; then
    echo "Starting Daphne server..."
    exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
elif [ "$1" = "worker" ]; then
    echo "Starting background worker..."
    exec python manage.py runworker --settings=config.settings_docker
elif [ "$1" = "migrate" ]; then
    echo "Running migrations only..."
    exec python manage.py migrate --settings=config.settings_docker
elif [ "$1" = "shell" ]; then
    echo "Starting Django shell..."
    exec python manage.py shell --settings=config.settings_docker
else
    echo "Starting Daphne server..."
    exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
fi