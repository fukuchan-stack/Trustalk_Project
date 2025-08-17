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
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
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

def _generate_draft(llm, model_name: str, transcript_text: str):
    print(f"LLM [Step 1/4]: Generating draft with {model_name}...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、会議の文字起こしを分析し、要点とアクションアイテムを抽出するアシスタントです。"),
        ("user", """以下の会議の文字起こしから、要約とToDoリストを作成してください。
# 文字起こし
{transcript}
# 命令
1. この会議の要約を3〜5個の箇条書きで作成してください。
2. この会議で発生したToDo（アクションアイテム）をリストアップしてください。
あなたの回答は、必ず以下のjson形式で返してください。
{{"summary": ["要約1", "要約2"], "todos": ["ToDo1", "ToDo2"]}}""")
    ])
    if model_name.startswith("gpt"):
        chain = prompt | llm.bind(response_format={"type": "json_object"})
    else:
        chain = prompt | llm
    return chain.invoke({"transcript": transcript_text})

def _review_draft(llm, model_name: str, transcript_text: str, draft: dict):
    print(f"LLM [Step 2/4]: Reviewing draft with {model_name}...")
    draft_summary = "\n".join(f"- {item}" for item in draft.get("summary", []))
    draft_todos = "\n".join(f"- {item}" for item in draft.get("todos", []))
    prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、AIアシスタントが作成した会議の要約とToDoリストを評価する、優秀な編集長です。"),
        ("user", """以下の「元の文字起こし」と、それに基づいてAIが作成した「ドラフト」をレビューしてください。
# 元の文字起こし
{transcript}
# ドラフト
## 要約
{summary}
## ToDoリスト
{todos}
# 命令
以下の観点に基づいて、このドラフトの良い点と改善点を具体的に指摘してください。
- 要約の忠実性
- ToDoの網羅性
- 全体的な明確さ
あなたのレビューコメントを簡潔に記述してください。""")
    ])
    chain = prompt | llm
    return chain.invoke({"transcript": transcript_text, "summary": draft_summary, "todos": draft_todos})

def _revise_draft(llm, model_name: str, transcript_text: str, draft: dict, review_feedback: str):
    print(f"LLM [Step 3/4]: Revising draft with {model_name}...")
    draft_summary = "\n".join(f"- {item}" for item in draft.get("summary", []))
    draft_todos = "\n".join(f"- {item}" for item in draft.get("todos", []))
    prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、編集長からのレビューフィードバックを元に、会議の要約とToDoリストを改善するアシスタントです。"),
        ("user", """以下の「元の文字起こし」、「最初のドラフト」、そして「編集長からのレビュー」をすべて考慮して、最終的な成果物を作成してください。
# 元の文字起こし
{transcript}
# 最初のドラフト
## 要約
{summary}
## ToDoリスト
{todos}
# 編集長からのレビュー
{feedback}
# 命令
レビューでの指摘事項を反映し、**最高の品質**の要約とToDoリストを生成してください。
あなたの回答は、必ず以下のjson形式で返してください。
{{"summary": ["改善された要約1"], "todos": ["改善されたToDo1"]}}""")
    ])
    if model_name.startswith("gpt"):
        chain = prompt | llm.bind(response_format={"type": "json_object"})
    else:
        chain = prompt | llm
    return chain.invoke({"transcript": transcript_text, "summary": draft_summary, "todos": draft_todos, "feedback": review_feedback})

def _evaluate_reliability(llm, model_name: str, transcript_text: str, final_summary: str):
    print(f"LLM [Step 4/4]: Evaluating reliability with {model_name}...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、AIが生成した要約を、元の文字起こしと比較して評価する厳格な評価者です。"),
        ("user", """以下の「元の文字起こし」と「AIによる要約」を比較してください。
# 元の文字起こし
{transcript}
# AIによる要約
{summary}
# 命令
以下の3つの観点で、要約の品質を0.0から1.0の範囲で採点してください。
1. **忠実性 (Faithfulness)**
2. **網羅性 (Comprehensiveness)**
3. **簡潔性 (Conciseness)**
あなたの評価を、以下のjson形式で返してください。
{{"faithfulness_score": 0.9, "comprehensiveness_score": 0.8, "conciseness_score": 1.0, "justification": "要約は概ね正確だが、Q4予算に関する言及が抜けている。"}}""")
    ])
    if model_name.startswith("gpt"):
        chain = prompt | llm.bind(response_format={"type": "json_object"})
    else:
        chain = prompt | llm
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
        
        scores = [evaluation.get(s, 0) for s in ["faithfulness_score", "comprehensiveness_score", "conciseness_score"]]
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