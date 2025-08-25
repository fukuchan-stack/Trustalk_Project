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

# ★★★ 修正点: sh -c を使って環境変数を展開するように変更 ★★★
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]