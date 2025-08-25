# ベースイメージとして、Python 3.11を使用します
FROM python:3.11-slim

# OSのパッケージリストを更新し、必要なツールをインストールします
RUN apt-get update && apt-get install -y ffmpeg build-essential cmake

# コンテナ内の作業ディレクトリを /app に設定します
WORKDIR /app

# プロジェクトのファイルをコンテナにコピーします
COPY . /app

# Pythonの依存関係をインストールします
# --no-cache-dir: pipのキャッシュを使わない
# --upgrade pip: pipを最新版にアップグレード
RUN pip install --no-cache-dir --upgrade pip && \
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r backend/requirements.txt

# RenderがFastAPIアプリケーションを動かすポートを公開します
EXPOSE 10000

# コンテナ起動時に実行するコマンドを定義します
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000", "--reload"]