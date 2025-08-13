# models.py
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel

# configからAPIキーを直接インポート
from config import OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY

def is_openai_model(model_name: str) -> bool:
    """モデル名がOpenAIのものか判定する"""
    return model_name.startswith("gpt")

def is_gemini_model(model_name: str) -> bool:
    """モデル名がGeminiのものか判定する"""
    return model_name.startswith("gemini")

def is_anthropic_model(model_name: str) -> bool:
    """モデル名がAnthropicのものか判定する"""
    return model_name.startswith("claude")

def get_llm_instance(model_name: str) -> BaseChatModel:
    """
    モデル名に基づいてLLMのインスタンスを生成して返す。
    APIキーの選択ロジックもこの関数内にカプセル化する。
    """
    if is_openai_model(model_name):
        return ChatOpenAI(model=model_name, api_key=OPENAI_API_KEY, temperature=0)
    elif is_gemini_model(model_name):
        # Geminiはシステムプロンプトの扱いに注意が必要なため、互換性オプションを有効にする
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=GOOGLE_API_KEY, temperature=0, convert_system_message_to_human=True)
    elif is_anthropic_model(model_name):
        return ChatAnthropic(model=model_name, anthropic_api_key=ANTHROPIC_API_KEY, temperature=0)
    else:
        raise ValueError(f"サポートされていないモデル、または不明なモデルです: {model_name}")

def invoke_model(model_name: str, prompt_template: str, inputs: dict) -> str:
    """プロンプトと入力を使用してモデルを呼び出し、テキストの応答を返す"""
    llm = get_llm_instance(model_name)
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    response = chain.invoke(inputs)
    return response.content
