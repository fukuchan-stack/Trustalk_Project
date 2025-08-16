# backend/rag_pipelines.py (カスタム評価ロジックを実装した最終版)

import pandas as pd
import numpy as np
import chardet
from io import BytesIO
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from models import get_llm

def _parse_csv_to_records(file, required_columns: list[str]):
    try:
        file_content = file.read()
        result = chardet.detect(file_content)
        encoding = result['encoding']
        print(f"--- Detected encoding: {encoding} with confidence {result['confidence']} ---")
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
    context_docs = []
    for rec in context_records:
        content = rec["context"]
        if isinstance(content, str) and content.strip():
            context_docs.append(Document(page_content=content))
    if not context_docs:
        raise ValueError("文脈CSVに、有効なコンテキストが見つかりませんでした。")
    print("--- RAG: Initializing embedding model (初回は時間がかかります) ---")
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    print("--- RAG: Creating FAISS vector store in batches ---")
    vector_store = None
    batch_size = 64
    for i in range(0, len(context_docs), batch_size):
        batch = context_docs[i:i + batch_size]
        if vector_store is None:
            print(f"--- RAG: Creating FAISS index with first batch (size: {len(batch)}) ---")
            vector_store = FAISS.from_documents(batch, embedding_model)
        else:
            print(f"--- RAG: Adding batch {i//batch_size + 1} to FAISS index (size: {len(batch)}) ---")
            vector_store.add_documents(batch)
    print("--- RAG: Vector store created successfully ---")
    return vector_store

def run_rag_benchmark_pipeline(qa_dataset: list, context_file, model_name: str):
    vector_store = create_vector_store(context_file)
    retriever = vector_store.as_retriever()
    template = "以下の文脈情報だけを使って、質問に答えてください。\n\n文脈:\n{context}\n\n質問:\n{question}\n\n回答:"
    prompt = ChatPromptTemplate.from_template(template)
    llm = get_llm(model_name)
    eval_llm = get_llm("gpt-4o-mini") 

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)
        
    rag_chain = ({"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser())
    
    # ★ 変更点: カスタム評価プロンプトを使用する
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
1.  **忠実性 (faithfulness):** AIの回答は、AIが参照した文脈の内容に完全に忠実ですか？文脈にない情報（ハルシネーション）を述べていたら減点してください。
2.  **関連性 (relevance):** AIの回答は、元の質問に的確に答えていますか？質問と無関係な内容を答えていたら減点してください。

あなたの評価を、以下のjson形式で返してください。
{{
  "faithfulness_score": 0.9,
  "relevance_score": 1.0
}}
""")
    ])

    evaluator_chain = evaluation_prompt | eval_llm.bind(response_format={"type": "json_object"}) | JsonOutputParser()

    results = []
    faithfulness_scores = []
    relevancy_scores = []
    print(f"--- RAG: Running benchmark for {len(qa_dataset)} questions ---")
    for item in qa_dataset:
        question, ground_truth = item['question'], item['ground_truth']
        print(f"--- RAG: Answering question: '{question[:30]}...' ---")
        retrieved_docs = retriever.invoke(question)
        generated_answer = rag_chain.invoke(question)
        print(f"--- RAG: Evaluating answer... ---")
        
        evaluation_result = evaluator_chain.invoke({
            "question": question,
            "context": format_docs(retrieved_docs),
            "prediction": generated_answer
        })

        current_faithfulness = evaluation_result.get('faithfulness_score', 0)
        current_relevancy = evaluation_result.get('relevance_score', 0)
        
        faithfulness_scores.append(current_faithfulness)
        relevancy_scores.append(current_relevancy)
        results.append({
            "question": question, "ground_truth": ground_truth, "generated_answer": generated_answer,
            "retrieved_contexts": [doc.page_content for doc in retrieved_docs],
            "faithfulness_score": current_faithfulness, "relevancy_score": current_relevancy,
        })
    
    print("--- RAG: Benchmark finished ---")
    final_scores = {
        "average_faithfulness": np.mean(faithfulness_scores) if faithfulness_scores else 0,
        "average_answer_relevancy": np.mean(relevancy_scores) if relevancy_scores else 0,
    }
    return {"results_by_question": results, "final_scores": final_scores}