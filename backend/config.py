# config.py

# RAG構成オプション
RAG_CONFIG_OPTIONS = [
    "Chanking",
    "Hybrid Search",
    "Prompt",
]

# 評価の閾値
TONIC_THRESHOLD = 2.0
COSINE_THRESHOLD = 0.8

# 評価・アシスタントに使用するモデルのリスト
EVAL_MODEL_OPTIONS = [
    "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo",
    "gemini-1.5-pro-latest", "gemini-1.5-flash-latest",
    "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307",
]
AGENT_MODEL_OPTIONS = [
    "gpt-4o", "gemini-1.5-pro-latest", "claude-3-opus-20240229",
]

# モデルごとのトークンコスト (1000トークンあたりのUSD)
MODEL_COSTS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gemini-1.5-pro-latest": {"input": 0.0035, "output": 0.0105},
    "gemini-1.5-flash-latest": {"input": 0.00035, "output": 0.00053},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
}

# GradioのDataFrameに表示するヘッダー
DF_HEADERS = [
    "ID", "タイムスタンプ", "モデル", "構成", "質問", "最終判定",
    "Faithfulness", "Answer Relevancy", "Context Precision", "Context Recall",
    "コスト(USD)", "正解", "生成回答", "検索された文脈"
]

# APIキーの読み込み
try:
    from google.colab import userdata
    OPENAI_API_KEY = userdata.get('OPENAI_API_KEY')
    GOOGLE_API_KEY = userdata.get('GOOGLE_API_KEY')
    ANTHROPIC_API_KEY = userdata.get('ANTHROPIC_API_KEY')
except (ImportError, ModuleNotFoundError):
    import os
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
