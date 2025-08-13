# Microsoftが提供する公式のdevcontainer用Debianイメージをベースにする
FROM mcr.microsoft.com/devcontainers/base:debian

# Dockerfile内で環境変数を設定し、apt-getが対話形式にならないようにする
ENV DEBIAN_FRONTEND=noninteractive

# 必要なシステムライブラリをインストール
# RUNコマンドはレイヤーを作成するため、一度にまとめて実行するのが効率的
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    cmake \
    python3-venv \
    # インストール後に不要なキャッシュを削除してイメージサイズを小さくする
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*