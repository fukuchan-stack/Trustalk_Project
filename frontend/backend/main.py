# backend/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import database
import whisper
import os
import uuid
import json
import torch
import subprocess
from pyannote.audio import Pipeline
from models import get_llm_instance
from config import MODEL_COSTS, HUGGING_FACE_HUB_TOKEN
from langchain_community.callbacks import get_openai_callback
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness

if HUGGING_FACE_HUB_TOKEN is None:
    raise ValueError("Hugging Faceのアクセストークンが設定されていません。Codespacesのシークレットを確認してください。")

database.init_db()
app = FastAPI()

# CORSミドルウェア
app.add_middleware(
    CORSMiddleware,
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    # ★ 修正点：正規表現を使い、あらゆるCodespacesのURLを許可する
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    allow_origin_regex=r"https?://.*\.app\.github\.dev", # httpとhttpsの両方、あらゆるgithub.devのサブドメインを許可
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "temp_audio"
os.makedirs(UPLOAD_DIR, exist_ok=True)

print("Whisperモデルをロード中...")
whisper_model = whisper.load_model("base")
print("Whisperモデルのロード完了。")

print("話者分離モデルをロード中...")
diarization_pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=HUGGING_FACE_HUB_TOKEN
)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
diarization_pipeline.to(device)
print("話者分離モデルのロード完了。")


@app.get("/")
def read_root():
    return {"message": "Backend is running!"}

@app.get("/api/history")
def get_history():
    db = database.SessionLocal()
    try:
        query = db.query(database.EvaluationLog).statement
        df = pd.read_sql(query, db.bind)
        return df.to_dict(orient='records')
    finally:
        db.close()

@app.post("/api/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    db = database.SessionLocal()
    temp_filepath = ""
    wav_filepath = ""
    try:
        # 1. ファイル保存とWAV変換
        file_extension = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_filepath = os.path.join(UPLOAD_DIR, temp_filename)
        with open(temp_filepath, "wb") as buffer:
            buffer.write(await file.read())
        wav_filename = f"{uuid.uuid4()}.wav"
        wav_filepath = os.path.join(UPLOAD_DIR, wav_filename)
        subprocess.run(['ffmpeg', '-i', temp_filepath, wav_filepath], check=True)

        # 2a. 話者分離を実行
        print("話者分離を実行中...")
        diarization = diarization_pipeline(wav_filepath)
        print("話者分離完了。")

        # 2b. Whisperで単語タイムスタンプ付き文字起こし
        print("タイムスタンプ付き文字起こしを実行中...")
        whisper_result = whisper_model.transcribe(wav_filepath, language="ja", word_timestamps=True)
        print("文字起こし完了。")

        # 3. 話者分離と文字起こし結果を統合
        print("話者情報と文字起こしを統合中...")
        speaker_mapping = {label: f"話者{i+1}" for i, label in enumerate(diarization.labels())}
        
        segments = whisper_result['segments']
        speaker_aware_transcript_parts = []
        current_speaker = None
        
        for segment in segments:
            if 'words' not in segment:
                continue
            for word in segment['words']:
                word_start_time = word['start']
                
                speaking_turn = None
                for turn, _, speaker_label in diarization.itertracks(yield_label=True):
                    if turn.start <= word_start_time < turn.end:
                        speaking_turn = speaker_mapping.get(speaker_label, "不明な話者")
                        break
                
                if speaking_turn is None:
                    speaking_turn = "不明な話者"

                if speaking_turn != current_speaker:
                    if speaker_aware_transcript_parts:
                        speaker_aware_transcript_parts.append("\n\n")
                    speaker_aware_transcript_parts.append(f"**{speaking_turn}:**\n")
                    current_speaker = speaking_turn
                
                speaker_aware_transcript_parts.append(word['word'])

        speaker_aware_transcript = "".join(speaker_aware_transcript_parts).strip()
        print("統合完了。")

        # 4. LLM処理
        model_name = "gpt-4o-mini"
        llm = get_llm_instance(model_name)
        cost = 0.0
        model_cost_info = MODEL_COSTS.get(model_name, {"input": 0, "output": 0})
        
        summary_prompt = ChatPromptTemplate.from_template("以下の会議の議事録を、重要なポイントを箇条書きで簡潔に要約してください。\n\n議事録:\n---\n{text}\n---")
        summary_chain = summary_prompt | llm | StrOutputParser()
        summary = ""
        with get_openai_callback() as cb_summary:
            summary = summary_chain.invoke({"text": speaker_aware_transcript})
            cost += (cb_summary.prompt_tokens * model_cost_info["input"] / 1000) + \
                    (cb_summary.completion_tokens * model_cost_info["output"] / 1000)
        
        todo_prompt = ChatPromptTemplate.from_template("""以下の会議の議事録から、アクションアイテム（誰が、いつまでに、何をするかというタスク）を抽出してください。\n以下のJSON形式のリストで回答してください。アクションアイテムが見つからない場合は空のリスト [] を返してください。\n\n[
          {{ "assignee": "担当者名", "task": "具体的なタスク内容", "due_date": "期日" }},
          {{ "assignee": "担当者名", "task": "具体的なタスク内容", "due_date": "期日" }}
        ]\n\n議事録:\n---\n{text}\n---""")
        todo_chain = todo_prompt | llm | StrOutputParser()
        todos = []
        with get_openai_callback() as cb_todo:
            todo_json_string = todo_chain.invoke({"text": speaker_aware_transcript})
            try:
                cleaned_string = todo_json_string.strip()
                if cleaned_string.endswith(','): cleaned_string = cleaned_string[:-1]
                if not cleaned_string.startswith('['): cleaned_string = '[' + cleaned_string
                if not cleaned_string.endswith(']'): cleaned_string = cleaned_string + ']'
                todos = json.loads(cleaned_string)
            except json.JSONDecodeError:
                todos = []
            cost += (cb_todo.prompt_tokens * model_cost_info["input"] / 1000) + \
                    (cb_todo.completion_tokens * model_cost_info["output"] / 1000)

        # 5. Ragas評価
        data_samples = { 'question': ["N/A"], 'answer': [summary], 'contexts': [[speaker_aware_transcript]] }
        dataset = Dataset.from_dict(data_samples)
        score = evaluate(dataset, metrics=[faithfulness])
        faithfulness_score = score["faithfulness"][0]

        # 6. DB保存
        new_log = database.EvaluationLog(model_name=model_name, rag_config="Audio-Diarization", question=f"Audio file: {file.filename}", ground_truth=speaker_aware_transcript, generated_answer=summary, retrieved_contexts=speaker_aware_transcript, final_judgement="O" if faithfulness_score > 0.8 else "X", faithfulness=faithfulness_score, cost_usd=cost, answer_relevancy=0, context_precision=0, context_recall=0, tonic_score=0, cosine_similarity=0, mlflow_judgement="")
        db.add(new_log)
        db.commit()
        
        return {
            "filename": file.filename,
            "transcribed_text": speaker_aware_transcript,
            "summary": summary,
            "faithfulness_score": faithfulness_score,
            "cost_usd": cost,
            "todos": todos
        }
    except Exception as e:
        db.rollback()
        print(f"エラーが発生しました: {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if os.path.exists(wav_filepath):
            os.remove(wav_filepath)
        db.close()

@app.get("/api/history/{log_id}")
def get_history_detail(log_id: int):
    db = database.SessionLocal()
    try:
        log = db.query(database.EvaluationLog).filter(database.EvaluationLog.id == log_id).first()
        if log is None:
            raise HTTPException(status_code=404, detail="Log not found")
        return log
    finally:
        db.close()