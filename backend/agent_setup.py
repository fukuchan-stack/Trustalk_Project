# agent_setup.py
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory

# 修正：get_llm_instanceのみをインポートする
from models import get_llm_instance

def initialize_agent_executor(state, model_name: str, tools: list):
    """
    指定されたモデル名でLangChainエージェントを初期化します。
    """
    if state is None:
        raise ValueError("アプリケーションの状態が初期化されていません。")

    # LLMの初期化ロジックを簡潔化
    try:
        # 修正：get_llm_instanceを呼び出すだけにする
        llm = get_llm_instance(model_name)
    except Exception as e:
        raise ValueError(f"LLMの初期化に失敗しました: {e}")

    # プロンプトの作成 (変更なし)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """あなたはRAG評価の結果データを分析するAIアシスタントです。
        以下のツールを適切に使い分け、ユーザーからの依頼に答えてください。
        - 質問には簡潔かつ明確に答えること。
        - グラフや分析結果を要求されたら、必ず対応するツールを呼び出すこと。
        - RAG構成の変更を指示されたら、'update_rag_config'ツールを使用して、次の評価からその設定が反映されるように変更すること。
        - ユーザーが評価の実行を依頼した場合、`run_evaluation_for_agent`ツールを呼び出すこと。
        """),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    
    # エージェントの作成 (変更なし)
    agent = create_openai_functions_agent(llm, tools, prompt)
    
    # Executorの作成 (変更なし)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        memory=ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True,
            chat_history=state.agent_memory_messages
        ),
        handle_parsing_errors=True
    )
    return executor
