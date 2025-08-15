# backend/models.py

import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

def get_llm(model_name: str) -> BaseChatModel:
    """
    モデル名に基づいて、適切なLLMクライアントのインスタンスを生成して返す。
    APIキーは環境変数から自動的に読み込まれる。
    """
    
    # モデル名からプロバイダー（'openai', 'google', 'anthropic'）を判定
    provider = "unknown"
    if model_name.startswith("gpt"):
        provider = "openai"
    elif model_name.startswith("gemini"):
        provider = "google"
    elif model_name.startswith("claude"):
        provider = "anthropic"

    # プロバイダーに応じてクライアントを初期化
    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            temperature=0,
            # 環境変数 OPENAI_API_KEY が自動で使われる
        )
    elif provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            # 環境変数 GOOGLE_API_KEY が自動で使われる
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model_name,
            temperature=0,
            # 環境変数 ANTHROPIC_API_KEY が自動で使われる
        )
    else:
        raise ValueError(f"サポートされていない、または不明なモデル名です: {model_name}")