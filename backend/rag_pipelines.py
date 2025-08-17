import pandas as pd
import numpy as np
import chardet
import json
from io import BytesIO
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from models import get_llm
from ai_pipelines import _extract_token_usage

def _parse_csv_to_records(file, required_columns: list[str]):
    try:
        file_content = file.read()
        result = chardet.detect(file_content)
        encoding = result.get('encoding', 'utf-8')
        df = pd.read_csv(BytesIO(file_content), encoding=encoding)
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"CSVに必須のカラム '{col}' が見つかりません。")
        return df.to_dict('records')
    except Exception as e:
        raise ValueError(f"CSVファイルの読み込みまたは解析に失敗しました: {e}")

def create_retriever(context_file, options: dict):
    print("--- RAG: Parsing context CSV ---")
    context_records = _parse_csv_to_records(context_file, required_columns=["context"])
    initial_docs = [Document(page_content=rec["context"]) for rec in context_records if isinstance(rec["context"], str) and rec["context"].strip()]
    if not initial_docs:
        raise ValueError("文脈CSVに、有効なコンテキストが見つかりませんでした。")

    docs_to_index = initial_docs
    if options.get("chunking"):
        print("--- RAG: Chunking context documents... ---")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs_to_index = text_splitter.split_documents(initial_docs)

    print("--- RAG: Initializing embedding model ---")
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    print("--- RAG: Creating retrievers ---")
    faiss_retriever = FAISS.from_documents(docs_to_index, embedding_model).as_retriever(search_kwargs={"k": 3})

    if options.get("hybridSearch"):
        print("--- RAG: Creating BM25 retriever for Hybrid Search... ---")
        bm25_retriever = BM25Retriever.from_documents(docs_to_index)
        bm25_retriever.k = 3
        ensemble_retriever = EnsembleRetriever(retrievers=[bm25_retriever, faiss_retriever], weights=[0.5, 0.5])
        print("--- RAG: Hybrid Search retriever created successfully ---")
        return ensemble_retriever
    else:
        print("--- RAG: Using standard vector retriever ---")
        return faiss_retriever

def get_rag_prompt(options: dict):
    if options.get("promptTuning"):
        print("--- RAG: Using advanced prompt template ---")
        template = """あなたは思考の連鎖（Chain of Thought）を用いて回答する、高度なAIアシスタントです。まずステップバイステップで考え、その後に最終的な回答を生成してください。
以下の文脈情報だけを使って、質問に答えてください。
文脈: 
{context}
質問: 
{question}
思考: （ここに思考を記述）
回答:
"""
    else:
        print("--- RAG: Using simple prompt template ---")
        template = "以下の文脈情報だけを使って、質問に答えてください。\n\n文脈:\n{context}\n\n質問:\n{question}\n\n回答:"
    
    return ChatPromptTemplate.from_template(template)

def run_rag_benchmark_pipeline(qa_dataset: list, context_file, model_name: str, advanced_options: dict):
    retriever = create_retriever(context_file, advanced_options)
    prompt = get_rag_prompt(advanced_options)
    llm = get_llm(model_name)
    eval_llm = get_llm("gpt-4o-mini") 
    def format_docs(docs): return "\n\n".join(doc.page_content for doc in docs)
    rag_chain = ({"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm)
    
    evaluation_prompt = ChatPromptTemplate.from_messages([("system", "あなたは、AIの回答を評価する厳格な評価者です。"),("user", """以下の「質問」、「AIが参照した文脈」、「AIの回答」を比較して、評価スコアを付けてください。
# 質問
{question}
# AIが参照した文脈
{context}
# AIの回答
{prediction}
# 命令
以下の2つの観点で、AIの回答の品質を0.0から1.0の範囲で採点してください。
1. **忠実性 (faithfulness)**
2. **関連性 (relevance)**
あなたの評価を、以下のjson形式で返してください。
{{"faithfulness_score": 0.9, "relevance_score": 1.0}}""")])
    evaluator_chain = evaluation_prompt | eval_llm.bind(response_format={"type": "json_object"})
    results, total_token_usage = [], {"input_tokens": 0, "output_tokens": 0}
    
    print(f"--- RAG: Running benchmark for {len(qa_dataset)} questions ---")
    for item in qa_dataset:
        question, ground_truth = item['question'], item['ground_truth']
        print(f"--- RAG: Answering question: '{question[:30]}...' ---")
        retrieved_docs_result = retriever.invoke(question)
        rag_chain_response = rag_chain.invoke(question)
        generated_answer = rag_chain_response.content
        usage = _extract_token_usage(rag_chain_response)
        total_token_usage["input_tokens"] += usage["input_tokens"]; total_token_usage["output_tokens"] += usage["output_tokens"]
        
        print(f"--- RAG: Evaluating answer... ---")
        evaluator_response = evaluator_chain.invoke({"question": question, "context": format_docs(retrieved_docs_result), "prediction": generated_answer})
        usage = _extract_token_usage(evaluator_response)
        total_token_usage["input_tokens"] += usage["input_tokens"]; total_token_usage["output_tokens"] += usage["output_tokens"]
        evaluation_result = json.loads(evaluator_response.content)
        
        current_faithfulness = evaluation_result.get('faithfulness_score', 0)
        current_relevancy = evaluation_result.get('relevance_score', 0)
        results.append({"question": question, "ground_truth": ground_truth, "generated_answer": generated_answer, "retrieved_contexts": [doc.page_content for doc in retrieved_docs_result], "faithfulness_score": current_faithfulness, "relevancy_score": current_relevancy})

    print("--- RAG: Benchmark finished ---")
    faithfulness_scores = [res.get('faithfulness_score', 0) for res in results]
    relevancy_scores = [res.get('relevancy_score', 0) for res in results]
    final_scores = {"average_faithfulness": np.mean(faithfulness_scores) if faithfulness_scores else 0, "average_answer_relevancy": np.mean(relevancy_scores) if relevancy_scores else 0}
    
    return {"results_by_question": results, "final_scores": final_scores, "token_usage": total_token_usage}