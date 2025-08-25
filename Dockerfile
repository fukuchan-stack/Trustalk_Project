# ベースイメージとして、Python 3.11を使用します
FROM python:3.11-slim

# OSのパッケージリストを更新し、必要なツールをインストールします
RUN apt-get update && apt-get install -y ffmpeg build-essential cmake

# コンテナ内の作業ディレクトリを /app に設定します
WORKDIR /app

# プロジェクトのファイルをコンテナにコピーします
COPY . /app

# Pythonの依存関係をインストールします
RUN pip install --no-cache-dir --upgrade pip && \
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r backend/requirements.txt

# RenderがFastAPIアプリケーションを動かすポートを公開します
EXPOSE 10000

# ★★★ 修正点: gunicornを使って起動するように変更 ★★★
WORKDIR /app/backend
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:10000"]