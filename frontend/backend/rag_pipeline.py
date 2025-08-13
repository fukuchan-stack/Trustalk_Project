# rag_pipeline.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.callbacks import get_openai_callback
from models import get_llm_instance
from config import MODEL_COSTS

def format_docs(docs):
    """検索されたドキュメントを文字列にフォーマットする"""
    return "\n\n".join(doc.page_content for doc in docs)

def run_rag_pipeline(retriever, model_name: str, question: str):
    """
    本格的なRAGパイプラインを実行し、回答、文脈、コストを返す。
    
    Args:
        retriever: LangChainのretrieverオブジェクト。
        model_name (str): 使用するモデルの名前。
        question (str): ユーザーの質問。
        
    Returns:
        tuple[str, str, float]: (生成された回答, 検索された文脈, 概算コスト)
    """
    llm = get_llm_instance(model_name)
    
    template = """
    あなたは親切なアシスタントです。以下の文脈情報のみを使って、最後の質問に答えてください。
    文脈情報で答えがわからない場合は、その旨を正直に伝えてください。

    文脈:
    {context}

    質問: {question}
    """
    prompt = ChatPromptTemplate.from_template(template)

    # LCELを使ってチェーンを構築
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # 回答と一緒に文脈も取得するためのチェーン
    # retrieverを2回呼ばないように、最初にretrieverの結果を保持する
    chain_with_context = RunnablePassthrough.assign(
        contexts_docs=lambda x: retriever.invoke(x["question"])
    ).assign(
        answer=lambda x: (
            {"context": format_docs(x["contexts_docs"]), "question": x["question"]}
            | prompt
            | llm
            | StrOutputParser()
        )
    )
    
    cost = 0.0
    # get_openai_callbackはOpenAIモデルでのみトークン数を正確に取得できる
    # 他モデルのコスト計算は概算または別途実装が必要
    with get_openai_callback() as cb:
        result = chain_with_context.invoke({"question": question})
        
        # コスト計算
        model_cost = MODEL_COSTS.get(model_name, {"input": 0, "output": 0})
        cost = (cb.prompt_tokens * model_cost["input"] / 1000) + \
               (cb.completion_tokens * model_cost["output"] / 1000)

    contexts_str = format_docs(result["contexts_docs"])
    return result["answer"], contexts_str, cost
