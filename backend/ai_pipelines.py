# backend/ai_pipelines.py (コスト計算対応版)

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_community.callbacks import get_openai_callback
from models import get_llm

def _generate_draft(llm, transcript_text: str):
    print("LLM [Step 1/4]: Generating draft...")
    llm_with_json = llm.bind(response_format={"type": "json_object"})
    prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、会議の文字起こしを分析し、要点とアクションアイテムを抽出するアシスタントです。"),
        ("user", """以下の会議の文字起こしから、要約とToDoリストを作成してください。

# 文字起こし
{transcript}

# 命令
1. この会議の要約を3〜5個の箇条書きで作成してください。
2. この会議で発生したToDo（アクションアイテム）をリストアップしてください。

あなたの回答は、必ず以下のjson形式で返してください。
{{
  "summary": ["要約1", "要約2"],
  "todos": ["ToDo1", "ToDo2"]
}}
""")
    ])
    chain = prompt | llm_with_json | JsonOutputParser()
    return chain.invoke({"transcript": transcript_text})

def _review_draft(llm, transcript_text: str, draft: dict):
    print("LLM [Step 2/4]: Reviewing draft...")
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
- 要約の忠実性: 要約は、元の文字起こしの内容と一致していますか？重要な情報が欠けていませんか？
- ToDoの網羅性: すべてのタスクが正しく抽出されていますか？担当者や期限が明確ですか？
- 全体的な明確さ: 表現は分かりやすいですか？

あなたのレビューコメントを簡潔に記述してください。
""")
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"transcript": transcript_text, "summary": draft_summary, "todos": draft_todos})

def _revise_draft(llm, transcript_text: str, draft: dict, review_feedback: str):
    print("LLM [Step 3/4]: Revising draft...")
    llm_with_json = llm.bind(response_format={"type": "json_object"})
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
{{
  "summary": ["改善された要約1", "改善された要約2"],
  "todos": ["改善されたToDo1", "改善されたToDo2"]
}}
""")
    ])
    chain = prompt | llm_with_json | JsonOutputParser()
    return chain.invoke({"transcript": transcript_text, "summary": draft_summary, "todos": draft_todos, "feedback": review_feedback})

def _evaluate_reliability(llm, transcript_text: str, final_summary: str):
    print("LLM [Step 4/4]: Evaluating reliability...")
    llm_with_json = llm.bind(response_format={"type": "json_object"})
    prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、AIが生成した要約を、元の文字起こしと比較して評価する厳格な評価者です。"),
        ("user", """以下の「元の文字起こし」と「AIによる要約」を比較してください。

# 元の文字起こし
{transcript}

# AIによる要約
{summary}

# 命令
以下の3つの観点で、要約の品質を0.0から1.0の範囲で採点してください。
1.  **忠実性 (Faithfulness):** 要約に、元の文字起こしにはない情報（ハルシネーション）が含まれていませんか？完全に忠実なら1.0、そうでないなら減点してください。
2.  **網羅性 (Comprehensiveness):** 要約は、元の文字起こしの主要なトピックをすべてカバーしていますか？重要な情報が欠けている場合は減点してください。
3.  **簡潔性 (Conciseness):** 要約は、冗長な表現がなく、簡潔にまとまっていますか？

あなたの評価を、以下のjson形式で返してください。
{{
  "faithfulness_score": 0.9,
  "comprehensiveness_score": 0.8,
  "conciseness_score": 1.0,
  "justification": "要約は概ね正確だが、Q4予算に関する言及が抜けているため網羅性を減点した。"
}}
""")
    ])
    chain = prompt | llm_with_json | JsonOutputParser()
    evaluation = chain.invoke({"transcript": transcript_text, "summary": final_summary})
    scores = [evaluation.get("faithfulness_score", 0), evaluation.get("comprehensiveness_score", 0), evaluation.get("conciseness_score", 0)]
    average_score = sum(scores) / len(scores) if scores else 0
    return {"score": average_score, "justification": evaluation.get("justification", "評価に失敗しました。")}

def run_self_improvement_pipeline(model_name: str, transcript_text: str):
    """
    「ドラフト生成 → レビュー → 改善 → 評価」のパイプライン全体を実行し、結果とトークン使用量を返す
    """
    try:
        llm = get_llm(model_name)
        
        with get_openai_callback() as cb:
            draft_result = _generate_draft(llm, transcript_text)
            review_feedback = _review_draft(llm, transcript_text, draft_result)
            final_result = _revise_draft(llm, transcript_text, draft_result, review_feedback)
            summary = "\n".join(f"- {item}" for item in final_result.get("summary", []))
            todos = final_result.get("todos", [])
            reliability_info = _evaluate_reliability(llm, transcript_text, summary)
            
            token_usage = {
                "input_tokens": cb.prompt_tokens,
                "output_tokens": cb.completion_tokens,
            }

        return summary, todos, reliability_info, token_usage

    except Exception as e:
        print(f"LLMパイプラインでエラーが発生しました: {e}")
        return "要約の生成に失敗しました。", ["ToDoの抽出に失敗しました。"], {"score": 0.0, "justification": "パイプラインエラー"}, {"input_tokens": 0, "output_tokens": 0}