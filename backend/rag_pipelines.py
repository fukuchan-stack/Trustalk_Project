# backend/rag_pipelines.py (コスト計算を修正した最終完成版)

import time
import json
import pandas as pd
import numpy as np
import chardet
from io import BytesIO
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from models import get_llm

def _extract_token_usage(response):
    """LangChainのレスポンスオブジェクトからトークン使用量を抽出する（全プロバイダー対応版）"""
    usage = {}
    if hasattr(response, 'response_metadata') and response.response_metadata:
        if "usage_metadata" in response.response_metadata:
            usage_meta = response.response_metadata["usage_metadata"]
            return {"input_tokens": usage_meta.get("prompt_token_count", 0), "output_tokens": usage_meta.get("candidates_token_count", 0)}
        elif "token_usage" in response.response_metadata:
            usage = response.response_metadata["token_usage"]
        elif "usage" in response.response_metadata:
            usage = response.response_metadata["usage"]
    return {"input_tokens": usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0), "output_tokens": usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)}

def _parse_csv_to_records(file, required_columns: list[str]):
    try:
        file_content = file.read()
        result = chardet.detect(file_content)
        encoding = result['encoding']
        df = pd.read_csv(BytesIO(file_content), encoding=encoding)
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"CSVに必須のカラム '{col}' が見つかりません。")
        return df.to_dict('records')
    except Exception as e:
        raise ValueError(f"CSVファイルの読み込みまたは解析に失敗しました: {e}")

def create_vector_store(context_file):
    print("--- RAG: Parsing context CSV ---")
    context_records = _parse_csv_to_records(context_file, required_columns=["context"])
    context_docs = [Document(page_content=rec["context"]) for rec in context_records if isinstance(rec["context"], str) and rec["context"].strip()]
    if not context_docs:
        raise ValueError("文脈CSVに、有効なコンテキストが見つかりませんでした。")
    print("--- RAG: Initializing embedding model ---")
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    print("--- RAG: Creating FAISS vector store ---")
    vector_store = FAISS.from_documents(context_docs, embedding_model)
    print("--- RAG: Vector store created successfully ---")
    return vector_store

def run_rag_benchmark_pipeline(qa_dataset: list, context_file, model_name: str):
    vector_store = create_vector_store(context_file)
    retriever = vector_store.as_retriever()
    template = "以下の文脈情報だけを使って、質問に答えてください。\n\n文脈:\n{context}\n\n質問:\n{question}\n\n回答:"
    prompt = ChatPromptTemplate.from_template(template)
    llm = get_llm(model_name)
    eval_llm = get_llm("gpt-4o-mini") 
    def format_docs(docs): return "\n\n".join(doc.page_content for doc in docs)
    
    # ★ 変更点: チェーンの最後にパーサーを付けず、生のレスポンスオブジェクトを受け取る
    rag_chain = ({"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm)
    
    evaluation_prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、AIの回答を評価する厳格な評価者です。"),
        ("user", """以下の「質問」、「AIが参照した文脈」、「AIの回答」を比較して、評価スコアを付けてください。
# 質問
{question}
# AIが参照した文脈
{context}
# AIの回答
{prediction}
# 命令
以下の2つの観点で、AIの回答の品質を0.0から1.0の範囲で採点してください。
1. **忠実性 (faithfulness):** AIの回答は、AIが参照した文脈の内容に完全に忠実ですか？
2. **関連性 (relevance):** AIの回答は、元の質問に的確に答えていますか？
あなたの評価を、以下のjson形式で返してください。
{{"faithfulness_score": 0.9, "relevance_score": 1.0}}""")
    ])
    # ★ 変更点: こちらもパーサーを付けない
    evaluator_chain = evaluation_prompt | eval_llm.bind(response_format={"type": "json_object"})
    
    results, total_token_usage = [], {"input_tokens": 0, "output_tokens": 0}
    print(f"--- RAG: Running benchmark for {len(qa_dataset)} questions ---")
    
    for item in qa_dataset:
        question, ground_truth = item['question'], item['ground_truth']
        print(f"--- RAG: Answering question: '{question[:30]}...' ---")
        
        retrieved_docs_result = retriever.invoke(question)
        
        rag_chain_response = rag_chain.invoke(question)
        generated_answer = rag_chain_response.content # .contentで文字列を取得
        usage = _extract_token_usage(rag_chain_response) # 生のレスポンスからトークンを抽出
        total_token_usage["input_tokens"] += usage["input_tokens"]
        total_token_usage["output_tokens"] += usage["output_tokens"]
        
        print(f"--- RAG: Evaluating answer... ---")
        evaluator_response = evaluator_chain.invoke({"question": question, "context": format_docs(retrieved_docs_result), "prediction": generated_answer})
        usage = _extract_token_usage(evaluator_response) # 生のレスポンスからトークンを抽出
        total_token_usage["input_tokens"] += usage["input_tokens"]
        total_token_usage["output_tokens"] += usage["output_tokens"]
        evaluation_result = json.loads(evaluator_response.content) # .contentで文字列を取得してからパース
        
        current_faithfulness = evaluation_result.get('faithfulness_score', 0)
        current_relevancy = evaluation_result.get('relevance_score', 0)
        results.append({"question": question, "ground_truth": ground_truth, "generated_answer": generated_answer, "retrieved_contexts": [doc.page_content for doc in retrieved_docs_result], "faithfulness_score": current_faithfulness, "relevancy_score": current_relevancy})

    print("--- RAG: Benchmark finished ---")
    faithfulness_scores = [res.get('faithfulness_score', 0) for res in results]
    relevancy_scores = [res.get('relevancy_score', 0) for res in results]
    final_scores = {"average_faithfulness": np.mean(faithfulness_scores) if faithfulness_scores else 0, "average_answer_relevancy": np.mean(relevancy_scores) if relevancy_scores else 0}
    
    return {"results_by_question": results, "final_scores": final_scores, "token_usage": total_token_usage}