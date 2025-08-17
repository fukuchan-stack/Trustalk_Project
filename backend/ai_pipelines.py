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
from langchain_core.output_parsers import StrOutputParser
from models import get_llm

def _extract_token_usage(response):
    """LangChainのレスポンスオブジェクトからトークン使用量を抽出する（全プロバイダー対応版）"""
    usage = {}
    if hasattr(response, 'response_metadata') and response.response_metadata:
        if "usage_metadata" in response.response_metadata: # Google Gemini
            usage_meta = response.response_metadata["usage_metadata"]
            return {"input_tokens": usage_meta.get("prompt_token_count", 0), "output_tokens": usage_meta.get("candidates_token_count", 0)}
        elif "token_usage" in response.response_metadata: # OpenAI
            usage = response.response_metadata["token_usage"]
        elif "usage" in response.response_metadata: # Anthropic Claude
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

def _generate_draft(llm, model_name, transcript_text):
    print(f"LLM [Step 1/4]: Generating draft with {model_name}...")
    prompt = ChatPromptTemplate.from_messages([("system", "あなたは、会議の文字起こしを分析し、要点とアクションアイテムを抽出するアシスタントです。"),("user", "以下の会議の文字起こしから、要約とToDoリストを作成してください。\n\n# 文字起こし\n{transcript}\n\n# 命令\n1. この会議の要約を3〜5個の箇条書きで作成してください。\n2. この会議で発生したToDo（アクションアイテム）をリストアップしてください。\n\nあなたの回答は、必ず以下のjson形式で返してください。\n{{\"summary\": [\"要約1\", \"要約2\"], \"todos\": [\"ToDo1\", \"ToDo2\"]}}")])
    if model_name.startswith("gpt"): chain = prompt | llm.bind(response_format={"type": "json_object"})
    else: chain = prompt | llm
    return chain.invoke({"transcript": transcript_text})

def _review_draft(llm, model_name, transcript_text, draft):
    print(f"LLM [Step 2/4]: Reviewing draft with {model_name}...")
    prompt = ChatPromptTemplate.from_messages([("system", "あなたは、AIアシスタントが作成した会議の要約とToDoリストを評価する、優秀な編集長です。"),("user", "以下の「元の文字起こし」と、それに基づいてAIが作成した「ドラフト」をレビューしてください。\n\n# 元の文字起こし\n{transcript}\n\n# ドラフト\n## 要約\n{summary}\n## ToDoリスト\n{todos}\n\n# 命令\n以下の観点に基づいて、このドラフトの良い点と改善点を具体的に指摘してください。\n- 要約の忠実性\n- ToDoの網羅性\n- 全体的な明確さ\n\nあなたのレビューコメントを簡潔に記述してください。")])
    chain = prompt | llm
    return chain.invoke({"transcript": transcript_text, "summary": "\n".join(f"- {item}" for item in draft.get("summary", [])), "todos": "\n".join(f"- {item}" for item in draft.get("todos", []))})

def _revise_draft(llm, model_name, transcript_text, draft, review_feedback):
    print(f"LLM [Step 3/4]: Revising draft with {model_name}...")
    prompt = ChatPromptTemplate.from_messages([("system", "あなたは、編集長からのレビューフィードバックを元に、会議の要約とToDoリストを改善するアシスタントです。"),("user", "以下の「元の文字起こし」、「最初のドラフト」、そして「編集長からのレビュー」をすべて考慮して、最終的な成果物を作成してください。\n\n# 元の文字起こし\n{transcript}\n\n# 最初のドラフト\n## 要約\n{summary}\n## ToDoリスト\n{todos}\n\n# 編集長からのレビュー\n{feedback}\n\n# 命令\nレビューでの指摘事項を反映し、**最高の品質**の要約とToDoリストを生成してください。\nあなたの回答は、必ず以下のjson形式で返してください。\n{{\"summary\": [\"改善された要約1\"], \"todos\": [\"改善されたToDo1\"]}}")])
    if model_name.startswith("gpt"): chain = prompt | llm.bind(response_format={"type": "json_object"})
    else: chain = prompt | llm
    return chain.invoke({"transcript": transcript_text, "summary": "\n".join(f"- {item}" for item in draft.get("summary", [])), "todos": "\n".join(f"- {item}" for item in draft.get("todos", [])), "feedback": review_feedback})

def _evaluate_reliability(llm, model_name, transcript_text, final_summary):
    print(f"LLM [Step 4/4]: Evaluating reliability with {model_name}...")
    prompt = ChatPromptTemplate.from_messages([("system", "あなたは、AIが生成した要約を、元の文字起こしと比較して評価する厳格な評価者です。"),("user", "以下の「元の文字起こし」と「AIによる要約」を比較してください。\n# 元の文字起こし\n{transcript}\n# AIによる要約\n{summary}\n# 命令\n以下の3つの観点で、要約の品質を0.0から1.0の範囲で採点してください。\n1. **忠実性 (Faithfulness)**\n2. **網羅性 (Comprehensiveness)**\n3. **簡潔性 (Conciseness)**\nあなたの評価を、以下のjson形式で返してください。\n{{\"faithfulness_score\": 0.9, \"comprehensiveness_score\": 0.8, \"conciseness_score\": 1.0, \"justification\": \"要約は概ね正確だが、Q4予算に関する言及が抜けている。\"}}")])
    if model_name.startswith("gpt"): chain = prompt | llm.bind(response_format={"type": "json_object"})
    else: chain = prompt | llm
    return chain.invoke({"transcript": transcript_text, "summary": final_summary})

def run_self_improvement_pipeline(model_name: str, transcript_text: str):
    try:
        llm = get_llm(model_name)
        total_token_usage = {"input_tokens": 0, "output_tokens": 0}
        
        response1 = _generate_draft(llm, model_name, transcript_text)
        usage = _extract_token_usage(response1); total_token_usage["input_tokens"] += usage["input_tokens"]; total_token_usage["output_tokens"] += usage["output_tokens"]
        draft_result = json.loads(response1.content)

        response2 = _review_draft(llm, model_name, transcript_text, draft_result)
        usage = _extract_token_usage(response2); total_token_usage["input_tokens"] += usage["input_tokens"]; total_token_usage["output_tokens"] += usage["output_tokens"]
        review_feedback = response2.content
        
        response3 = _revise_draft(llm, model_name, transcript_text, draft_result, review_feedback)
        usage = _extract_token_usage(response3); total_token_usage["input_tokens"] += usage["input_tokens"]; total_token_usage["output_tokens"] += usage["output_tokens"]
        final_result = json.loads(response3.content)

        summary = "\n".join(f"- {item}" for item in final_result.get("summary", []))
        todos = final_result.get("todos", [])
        
        response4 = _evaluate_reliability(llm, model_name, transcript_text, summary)
        usage = _extract_token_usage(response4); total_token_usage["input_tokens"] += usage["input_tokens"]; total_token_usage["output_tokens"] += usage["output_tokens"]
        evaluation = json.loads(response4.content)
        
        scores = [evaluation.get("faithfulness_score", 0), evaluation.get("comprehensiveness_score", 0), evaluation.get("conciseness_score", 0)]
        average_score = sum(scores) / len(scores) if scores else 0
        reliability_info = {"score": average_score, "justification": evaluation.get("justification", "評価に失敗しました。")}
        
        return summary, todos, reliability_info, total_token_usage
    except Exception as e:
        print(f"LLMパイプラインでエラーが発生しました ({model_name}): {e}")
        return "要約の生成に失敗しました。", ["ToDoの抽出に失敗しました。"], {"score": 0.0, "justification": f"パイプラインエラー: {e}"}, {"input_tokens": 0, "output_tokens": 0}

def run_benchmark_pipeline(transcript_text: str, models_to_run: list[str]):
    benchmark_results = []
    for model_name in models_to_run:
        print(f"\n--- Starting benchmark for model: {model_name} ---")
        start_time = time.time()
        summary, todos, reliability, token_usage = run_self_improvement_pipeline(model_name=model_name, transcript_text=transcript_text)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"--- Finished benchmark for {model_name} in {execution_time:.2f} seconds ---")
        benchmark_results.append({"model_name": model_name, "summary": summary, "todos": todos, "reliability": reliability, "token_usage": token_usage, "execution_time": execution_time})
    return benchmark_results

def run_rag_benchmark_pipeline(qa_dataset: list, context_file, model_name: str):
    vector_store = create_vector_store(context_file)
    retriever = vector_store.as_retriever()
    template = "以下の文脈情報だけを使って、質問に答えてください。\n\n文脈:\n{context}\n\n質問:\n{question}\n\n回答:"
    prompt = ChatPromptTemplate.from_template(template)
    llm = get_llm(model_name)
    eval_llm = get_llm("gpt-4o-mini") 
    def format_docs(docs): return "\n\n".join(doc.page_content for doc in docs)
    rag_chain = ({"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm)
    
    evaluation_prompt = ChatPromptTemplate.from_messages([("system", "あなたは、AIの回答を評価する厳格な評価者です。"),("user", "以下の「質問」、「AIが参照した文脈」、「AIの回答」を比較して、評価スコアを付けてください。\n# 質問\n{question}\n# AIが参照した文脈\n{context}\n# AIの回答\n{prediction}\n# 命令\n以下の2つの観点で、AIの回答の品質を0.0から1.0の範囲で採点してください。\n1. **忠実性 (faithfulness)**\n2. **関連性 (relevance)**\nあなたの評価を、以下のjson形式で返してください。\n{{\"faithfulness_score\": 0.9, \"relevance_score\": 1.0}}")])
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
        total_token_usage["input_tokens"] += usage["input_tokens"]
        total_token_usage["output_tokens"] += usage["output_tokens"]
        
        print(f"--- RAG: Evaluating answer... ---")
        evaluator_response = evaluator_chain.invoke({"question": question, "context": format_docs(retrieved_docs_result), "prediction": generated_answer})
        usage = _extract_token_usage(evaluator_response)
        total_token_usage["input_tokens"] += usage["input_tokens"]
        total_token_usage["output_tokens"] += usage["output_tokens"]
        evaluation_result = json.loads(evaluator_response.content)
        
        current_faithfulness = evaluation_result.get('faithfulness_score', 0)
        current_relevancy = evaluation_result.get('relevance_score', 0)
        results.append({"question": question, "ground_truth": ground_truth, "generated_answer": generated_answer, "retrieved_contexts": [doc.page_content for doc in retrieved_docs_result], "faithfulness_score": current_faithfulness, "relevancy_score": current_relevancy})

    print("--- RAG: Benchmark finished ---")
    faithfulness_scores = [res.get('faithfulness_score', 0) for res in results]
    relevancy_scores = [res.get('relevancy_score', 0) for res in results]
    final_scores = {"average_faithfulness": np.mean(faithfulness_scores) if faithfulness_scores else 0, "average_answer_relevancy": np.mean(relevancy_scores) if relevancy_scores else 0}
    
    return {"results_by_question": results, "final_scores": final_scores, "token_usage": total_token_usage}