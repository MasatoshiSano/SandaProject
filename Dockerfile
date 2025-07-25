# Python 3.10ベースイメージ
FROM python:3.10-slim

# 環境変数を設定
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 作業ディレクトリを設定
WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        gettext \
        curl \
        netcat-openbsd \
        wget \
        unzip \
        libaio1 \
        && rm -rf /var/lib/apt/lists/*

# Node.js（claude codeに必要）をインストール
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code

# Oracle Instant Clientをインストール
RUN wget https://download.oracle.com/otn_software/linux/instantclient/2112000/instantclient-basic-linux.x64-21.12.0.0.0dbru.zip
RUN wget https://download.oracle.com/otn_software/linux/instantclient/2112000/el9/instantclient-sdk-linux.x64-21.12.0.0.0dbru.zip
RUN unzip instantclient-basic-linux.x64-21.12.0.0.0dbru.zip \
    && unzip instantclient-sdk-linux.x64-21.12.0.0.0dbru.zip \
    && mv instantclient_21_12 /opt/oracle \
    && rm *.zip \
    && echo /opt/oracle >> /etc/ld.so.conf.d/oracle-instantclient.conf \
    && ldconfig

# Oracle環境変数を設定
ENV ORACLE_HOME=/opt/oracle
ENV LD_LIBRARY_PATH=/opt/oracle:$LD_LIBRARY_PATH
ENV PATH=/opt/oracle:$PATH

# Pythonの依存関係をインストール
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . /app/

# スクリプトファイルの存在確認とデバッグ
RUN ls -la /app/scripts/ || echo "Scripts directory not found"

# スクリプト用の実行権限を付与
RUN chmod +x /app/scripts/entrypoint.sh

# 静的ファイルとメディアファイル用のディレクトリを作成
RUN mkdir -p /app/staticfiles /app/media

# 静的ファイルを収集（エラー時は継続）
RUN python manage.py collectstatic --noinput --settings=config.settings_docker || echo "Static files collection failed, will retry at runtime"

# ポート8000を公開
EXPOSE 8000

# エントリーポイントスクリプトを実行
ENTRYPOINT ["/app/scripts/entrypoint.sh"]