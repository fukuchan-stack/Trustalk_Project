# backend/ai_pipelines.py (LangChainを使ったマルチモデル対応版)

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from models import get_llm

def _generate_draft(model_name: str, transcript_text: str):
    """ステップ1: 文字起こしから要約とToDoの「ドラフト」を生成する"""
    print(f"LLM [Step 1/3]: Generating draft with {model_name}...")
    
    llm = get_llm(model_name)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "あなたは、会議の文字起こしを分析し、要点とアクションアイテムを抽出するアシスタントです。"),
        ("user", """以下の会議の文字起こしから、要約とToDoリストを作成してください。

# 文字起こし
{transcript}

# 命令
1. この会議の要約を3〜5個の箇条書きで作成してください。
2. この会議で発生したToDo（アクションアイテム）をリストアップしてください。

あなたの回答は、必ず以下のJSON形式で返してください。
{{
  "summary": ["要約1", "要約2"],
  "todos": ["ToDo1", "ToDo2"]
}}
""")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({"transcript": transcript_text})

def _review_draft(model_name: str, transcript_text: str, draft: dict):
    """ステップ2: 生成されたドラフトをAI自身がレビューし、改善点を指摘する"""
    print(f"LLM [Step 2/3]: Reviewing draft with {model_name}...")

    llm = get_llm(model_name)
    
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
    return chain.invoke({
        "transcript": transcript_text,
        "summary": draft_summary,
        "todos": draft_todos
    })

def _revise_draft(model_name: str, transcript_text: str, draft: dict, review_feedback: str):
    """ステップ3: レビュー結果を元に、最終的な成果物を生成する"""
    print(f"LLM [Step 3/3]: Revising draft with {model_name}...")

    llm = get_llm(model_name)
    
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
あなたの回答は、必ず以下のJSON形式で返してください。
{{
  "summary": ["改善された要約1", "改善された要約2"],
  "todos": ["改善されたToDo1", "改善されたToDo2"]
}}
""")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({
        "transcript": transcript_text,
        "summary": draft_summary,
        "todos": draft_todos,
        "feedback": review_feedback
    })

def run_self_improvement_pipeline(model_name: str, transcript_text: str):
    """
    「ドラフト生成 → レビュー → 改善」のパイプライン全体を実行するメイン関数。
    """
    try:
        draft_result = _generate_draft(model_name, transcript_text)
        review_feedback = _review_draft(model_name, transcript_text, draft_result)
        final_result = _revise_draft(model_name, transcript_text, draft_result, review_feedback)

        summary = "\n".join(f"- {item}" for item in final_result.get("summary", []))
        todos = final_result.get("todos", [])
        
        return summary, todos

    except Exception as e:
        print(f"LLMパイプラインでエラーが発生しました: {e}")
        # エラーが発生した場合は、空の情報を返す
        return "要約の生成に失敗しました。", ["ToDoの抽出に失敗しました。"]