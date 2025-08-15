# backend/cost_calculator.py

# 2025年8月時点のおおよそのドル円レートを固定値として使用
# 本番環境では、APIなどでリアルタイムに取得するのが望ましいです
USD_TO_JPY_RATE = 145.0

# 各AIモデルの料金表 (100万トークンあたりのUSD)
# 注: 料金は変動する可能性があるため、これは実装時点での概算です
MODEL_PRICES_PER_MILLION_TOKENS = {
    # OpenAI
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    # Google
    "gemini-1.5-flash-latest": {"input": 0.35, "output": 1.05},
    "gemini-1.5-pro-latest": {"input": 3.50, "output": 10.50},
    # Anthropic
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
}

# Whisperの料金 (1分あたりのUSD)
# whisper-timestampedはローカルで実行されるためAPIコストは0ですが、
# 将来的にOpenAIのAPI版に切り替えることを想定し、計算ロジックの枠組みを用意しておきます。
WHISPER_PRICE_PER_MINUTE = 0.00 # ローカル実行のため0

def calculate_cost_in_jpy(model_name: str, total_input_tokens: int, total_output_tokens: int, audio_duration_seconds: float) -> float:
    """
    使用したトークン数と音声の長さから、概算コストを日本円で計算する。
    """
    
    # 1. LLMのコストを計算 (USD)
    prices = MODEL_PRICES_PER_MILLION_TOKENS.get(model_name)
    if not prices:
        print(f"警告: モデル '{model_name}' の料金情報が見つかりません。")
        llm_cost_usd = 0.0
    else:
        input_cost = (total_input_tokens / 1_000_000) * prices["input"]
        output_cost = (total_output_tokens / 1_000_000) * prices["output"]
        llm_cost_usd = input_cost + output_cost

    # 2. Whisperのコストを計算 (USD)
    audio_duration_minutes = audio_duration_seconds / 60.0
    whisper_cost_usd = audio_duration_minutes * WHISPER_PRICE_PER_MINUTE
    
    # 3. 合計コストを日本円に換算
    total_cost_usd = llm_cost_usd + whisper_cost_usd
    total_cost_jpy = total_cost_usd * USD_TO_JPY_RATE
    
    print(f"Cost Calculated: LLM Tokens (in:{total_input_tokens}, out:{total_output_tokens}), Audio Duration: {audio_duration_seconds:.2f}s, Total Cost: ¥{total_cost_jpy:.4f}")
    
    return total_cost_jpy