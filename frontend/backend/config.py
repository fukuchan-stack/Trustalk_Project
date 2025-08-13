# backend/config.py
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む（ローカル開発用）
load_dotenv()

# APIキーを環境変数から取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ★ 修正点：Hugging Faceのトークンを環境変数から取得する行を追加
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★
HUGGING_FACE_HUB_TOKEN = os.getenv("HUGGING_FACE_HUB_TOKEN")


# モデルごとのコスト情報（1000トークンあたりのドル価格）
MODEL_COSTS = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gemini-1.5-pro-latest": {"input": 0.0035, "output": 0.0105},
    "gemini-1.5-flash-latest": {"input": 0.00035, "output": 0.00105},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
}