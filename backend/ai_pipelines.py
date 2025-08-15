# backend/ai_pipelines.py (自己レビュー機能付き)

import json
from openai import OpenAI

def _generate_draft(client: OpenAI, transcript_text: str):
    """ステップ1: 文字起こしから要約とToDoの「ドラフト」を生成する"""
    print("LLM [Step 1/3]: Generating draft...")
    
    system_prompt = "あなたは、会議の文字起こしを分析し、要点とアクションアイテムを抽出するアシスタントです。"
    human_prompt = f"""以下の会議の文字起こしから、要約とToDoリストを作成してください。

# 文字起こし
{transcript_text}

# 命令
1. この会議の要約を3〜5個の箇条書きで作成してください。
2. この会議で発生したToDo（アクションアイテム）をリストアップしてください。

あなたの回答は、以下のJSON形式で返してください。
{{
  "summary": ["要約1", "要約2"],
  "todos": ["ToDo1", "ToDo2"]
}}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
    )
    draft_str = response.choices[0].message.content
    return json.loads(draft_str)


def _review_draft(client: OpenAI, transcript_text: str, draft: dict):
    """ステップ2: 生成されたドラフトをAI自身がレビューし、改善点を指摘する"""
    print("LLM [Step 2/3]: Reviewing draft...")
    
    draft_summary = "\n".join(f"- {item}" for item in draft.get("summary", []))
    draft_todos = "\n".join(f"- {item}" for item in draft.get("todos", []))

    system_prompt = "あなたは、AIアシスタントが作成した会議の要約とToDoリストを評価する、優秀な編集長です。"
    human_prompt = f"""以下の「元の文字起こし」と、それに基づいてAIが作成した「ドラフト」をレビューしてください。
    
# 元の文字起こし
{transcript_text}

# ドラフト
## 要約
{draft_summary}
## ToDoリスト
{draft_todos}

# 命令
以下の観点に基づいて、このドラフトの良い点と改善点を具体的に指摘してください。
- **要約の忠実性:** 要約は、元の文字起こしの内容と一致していますか？重要な情報が欠けていませんか？
- **ToDoの網羅性:** すべてのタスクが正しく抽出されていますか？担当者や期限が明確ですか？
- **全体的な明確さ:** 表現は分かりやすいですか？

あなたのレビュー結果を、以下のJSON形式で返してください。
{{
  "review_feedback": "（ここに具体的なレビューコメントを記述）"
}}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
    )
    review_str = response.choices[0].message.content
    return json.loads(review_str)


def _revise_draft(client: OpenAI, transcript_text: str, draft: dict, review_feedback: str):
    """ステップ3: レビュー結果を元に、最終的な成果物を生成する"""
    print("LLM [Step 3/3]: Revising draft based on feedback...")

    draft_summary = "\n".join(f"- {item}" for item in draft.get("summary", []))
    draft_todos = "\n".join(f"- {item}" for item in draft.get("todos", []))

    system_prompt = "あなたは、編集長からのレビューフィードバックを元に、会議の要約とToDoリストを改善するアシスタントです。"
    human_prompt = f"""以下の「元の文字起こし」、「最初のドラフト」、そして「編集長からのレビュー」をすべて考慮して、最終的な成果物を作成してください。

# 元の文字起こし
{transcript_text}

# 最初のドラフト
## 要約
{draft_summary}
## ToDoリスト
{draft_todos}

# 編集長からのレビュー
{review_feedback}

# 命令
レビューでの指摘事項を反映し、**最高の品質**の要約とToDoリストを生成してください。
あなたの回答は、以下のJSON形式で返してください。
{{
  "summary": ["改善された要約1", "改善された要約2"],
  "todos": ["改善されたToDo1", "改善されたToDo2"]
}}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": human_prompt}
        ]
    )
    final_str = response.choices[0].message.content
    return json.loads(final_str)


def run_self_improvement_pipeline(client: OpenAI, transcript_text: str):
    """
    「ドラフト生成 → レビュー → 改善」のパイプライン全体を実行するメイン関数。
    """
    try:
        # ステップ1: ドラフト生成
        draft_result = _generate_draft(client, transcript_text)
        
        # ステップ2: ドラフトのレビュー
        review_result = _review_draft(client, transcript_text, draft_result)
        review_feedback = review_result.get("review_feedback", "")
        
        # ステップ3: レビューを元に改善
        final_result = _revise_draft(client, transcript_text, draft_result, review_feedback)

        # 最終的な出力を整形
        summary = "\n".join(f"- {item}" for item in final_result.get("summary", []))
        todos = final_result.get("todos", [])
        
        return summary, todos

    except Exception as e:
        print(f"LLMパイプラインでエラーが発生しました: {e}")
        return "要約の生成に失敗しました。", ["ToDoの抽出に失敗しました。"]