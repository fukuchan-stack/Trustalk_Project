# backend/models.py

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

def get_llm(model_name: str) -> BaseChatModel:
    """
    モデル名に基づいて、適切なLLMクライアントのインスタンスを生成して返す。
    """
    
    provider = "unknown"
    if model_name.startswith("gpt"):
        provider = "openai"
    elif model_name.startswith("gemini"):
        provider = "google"
    elif model_name.startswith("claude"):
        provider = "anthropic"

    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            temperature=0,
        )
    elif provider == "google":
        # ★ 変更点: convert_system_message_to_human=True を削除
        return ChatGoogleGenerativeAI(model=model_name, temperature=0)
    elif provider == "anthropic":
        return ChatAnthropic(model=model_name, temperature=0)
    else:
        raise ValueError(f"サポートされていない、または不明なモデル名です: {model_name}")