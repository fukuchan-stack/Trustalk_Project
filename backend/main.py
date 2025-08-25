import os
import uuid
import json
import torch
import traceback
import subprocess
import re
import threading
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pyannote.audio import Pipeline
import whisper_timestamped as whisper
from ai_pipelines import run_self_improvement_pipeline, run_benchmark_pipeline
from cost_calculator import calculate_cost_in_jpy
from io import BytesIO

# --- 追加機能のためのインポート ---
import asana
from asana.rest import ApiException
from knowledge_base_manager import KnowledgeBaseManager
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from models import get_llm

# --- 環境変数 ---
HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise ValueError("環境変数 HF_TOKEN が設定されていません。")

# --- AIモデルのグローバル変数 (遅延読み込み) ---
device = "cuda" if torch.cuda.is_available() else "cpu"
whisper_model = None
diarization_pipeline = None
whisper_lock = threading.Lock()
pyannote_lock = threading.Lock()

# --- モデル読み込み関数 ---
def load_whisper_model():
    global whisper_model
    with whisper_lock:
        if whisper_model is None:
            print("Whisper: Loading 'base' model for the first time...")
            whisper_model = whisper.load_model("base", device=device)
            print("Whisper: Model loaded successfully.")

def load_pyannote_pipeline():
    global diarization_pipeline
    with pyannote_lock:
        if diarization_pipeline is None:
            print("Pyannote: Loading diarization pipeline for the first time...")
            diarization_pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=HF_TOKEN).to(torch.device(device))
            print("Pyannote: Diarization pipeline loaded successfully.")

# --- FastAPIアプリケーションのセットアップ ---
app = FastAPI(title="Trustalk API", version="3.0.0")

# ★★★ 修正箇所: 環境変数から許可オリジンを読み込む ★★★
allowed_origins_str = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = allowed_origins_str.split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# --- ナレッジベースとLLMの準備 ---
kb_manager = KnowledgeBaseManager()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# --- ヘルパー関数 ---
def merge_results(diarization, transcription):
    if not diarization: return "話者分離パイプラインが利用できません。", transcription.get("text", "")
    word_speakers, current_speaker, current_speech = [], None, ""
    for segment in transcription.get("segments", []):
        for word in segment.get("words", []):
            speaker_label = "UNKNOWN"
            try:
                cropped_annotation = diarization.crop(word)
                if cropped_annotation:
                    speaker_turn = cropped_annotation.get_timeline().support().pop(0)
                    speaker_label = speaker_turn[2]
            except (IndexError, KeyError): speaker_label = "UNKNOWN"
            word_speakers.append({'word': word.get('text', ''), 'speaker': speaker_label})
    if not word_speakers: return "発言が見つかりませんでした。", transcription.get("text", "")
    full_transcript_with_speakers, current_speaker, current_speech = "", word_speakers[0]['speaker'], ""
    for item in word_speakers:
        word, speaker = item['word'], item['speaker']
        if speaker != current_speaker:
            full_transcript_with_speakers += f"**{current_speaker}**: {current_speech.strip()}\n\n"; current_speech = ""
        current_speech += word + " "; current_speaker = speaker
    if current_speech: full_transcript_with_speakers += f"**{current_speaker}**: {current_speech.strip()}\n"
    return full_transcript_with_speakers.strip(), transcription.get("text", "")

# --- Pydanticモデル定義 ---
class DeleteHistoryRequest(BaseModel):
    ids: List[str]

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str

class SpeakerContribution(BaseModel):
    name: str
    value: int

class DashboardData(BaseModel):
    speaker_contributions: list[SpeakerContribution]
    
class AsanaExportRequest(BaseModel):
    task_name: str
    notes: str | None = None

class AsanaExportResponse(BaseModel):
    message: str
    task_url: str


# --- APIエンドポイント ---
@app.get("/", summary="APIのヘルスチェック")
def read_root(): return {"status": "ok"}

@app.post("/analyze", summary="音声ファイルの分析")
async def analyze_audio(file: UploadFile = File(...), model_name: str = Form("gpt-4o-mini")):
    load_whisper_model(); load_pyannote_pipeline()
    original_filename, temp_file_path = file.filename, f"/tmp/{uuid.uuid4()}_{file.filename}"
    wav_file_path = f"{os.path.splitext(temp_file_path)[0]}.wav"
    try:
        with open(temp_file_path, "wb") as buffer: contents = await file.read(); buffer.write(contents)
        command = ["ffmpeg", "-i", temp_file_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_file_path]; subprocess.run(command, check=True, capture_output=True, text=True)
        audio = whisper.load_audio(wav_file_path)
        audio_duration_seconds = len(audio) / whisper.audio.SAMPLE_RATE
        transcription_result = whisper.transcribe(whisper_model, audio, language="ja", detect_disfluencies=True)
        diarization_result = diarization_pipeline(wav_file_path)
        speakers_text, transcript_text = merge_results(diarization_result, transcription_result)
        cleaned_text = re.sub(r'[\(\[].*?[\)\]]', '', transcript_text or "").strip()
        if len(cleaned_text) < 10:
            summary_text, todos_list, reliability_info, token_usage = "- 音声が短すぎるため要約できません。", [], {"score": 0.0, "justification": "評価できません。"}, {"input_tokens": 0, "output_tokens": 0}
        else:
            summary_text, todos_list, reliability_info, token_usage = run_self_improvement_pipeline(model_name, transcript_text)
        calculated_cost_jpy = calculate_cost_in_jpy(model_name=model_name, total_input_tokens=token_usage.get("input_tokens", 0), total_output_tokens=token_usage.get("output_tokens", 0), audio_duration_seconds=audio_duration_seconds)
        result = { "id": str(uuid.uuid4()), "createdAt": datetime.now(timezone.utc).isoformat(), "originalFilename": original_filename, "model_name": model_name, "transcript": transcript_text if transcript_text and transcript_text.strip() else "有効な音声が検出されませんでした。", "summary": summary_text, "todos": todos_list, "speakers": speakers_text, "cost": calculated_cost_jpy, "reliability": reliability_info }
        history_file_path = os.path.join(HISTORY_DIR, f"{result['id']}.json")
        with open(history_file_path, "w", encoding="utf-8") as f: json.dump(result, f, ensure_ascii=False, indent=4)
        return JSONResponse(content=result)
    except Exception as e:
        print(traceback.format_exc()); raise HTTPException(status_code=500, detail=f"分析中に予期せぬエラー: {str(e)}")
    finally:
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        if os.path.exists(wav_file_path): os.remove(wav_file_path)

@app.post("/api/ask-knowledge-base", response_model=AskResponse, tags=["Knowledge Base"])
async def ask_knowledge_base(request: AskRequest):
    try:
        context_docs = kb_manager.search_knowledge_base(request.question)
        context_text = "\n\n---\n\n".join(context_docs)
        prompt_template = ChatPromptTemplate.from_template(
            """あなたはTrustalkプロジェクトの優秀なAIアシスタントです。
過去のミーティング議事録から検索された以下の「コンテキスト情報」のみに基づいて、ユーザーの「質問」に日本語で回答してください。
コンテキスト情報に答えがない場合は、「ナレッジベースには関連する情報が見つかりませんでした。」と回答してください。

# コンテキスト情報
{context}

# 質問
{question}
"""
        )
        prompt = prompt_template.format(context=context_text, question=request.question)
        response_message = llm.invoke(prompt)
        answer = response_message.content
        return AskResponse(answer=answer)
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AIアシスタント処理中にエラーが発生しました: {str(e)}")

@app.get("/api/dashboard/{analysis_id}", response_model=DashboardData, tags=["Dashboard"])
async def get_dashboard_data(analysis_id: str):
    history_file_path = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
    if not os.path.exists(history_file_path):
        raise HTTPException(status_code=404, detail="分析履歴が見つかりません。")
    try:
        with open(history_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        speakers_text = data.get("speakers", "")
        matches = re.findall(r"\*\*(.*?)\*\*:\s*(.*?)(?=\n\n\*\*|$)", speakers_text, re.DOTALL)
        contribution_data = {}
        for speaker, speech in matches:
            speech_length = len(speech.strip())
            contribution_data[speaker] = contribution_data.get(speaker, 0) + speech_length
        speaker_contributions = [{"name": name, "value": value} for name, value in contribution_data.items()]
        return DashboardData(speaker_contributions=speaker_contributions)
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"ダッシュボードデータの生成中にエラーが発生しました: {str(e)}")

@app.post("/api/export/asana", response_model=AsanaExportResponse, tags=["External Tools"])
async def export_todo_to_asana(request: AsanaExportRequest):
    ASANA_ACCESS_TOKEN = os.getenv("ASANA_ACCESS_TOKEN")
    if not ASANA_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Asanaのアクセストークンがサーバーに設定されていません。")

    ASANA_WORKSPACE_GID = "1211111431628203"
    ASANA_PROJECT_GID = "1211111199090161"

    if "YOUR_" in ASANA_WORKSPACE_GID or "YOUR_" in ASANA_PROJECT_GID:
       raise HTTPException(status_code=500, detail="AsanaのワークスペースIDまたはプロジェクトIDが設定されていません。")
    try:
        configuration = asana.Configuration()
        configuration.access_token = ASANA_ACCESS_TOKEN
        api_client = asana.ApiClient(configuration)
        
        tasks_api_instance = asana.TasksApi(api_client)
        
        task_data_body = { "data": { "name": request.task_name, "notes": request.notes or "Trustalkから作成されました。", "workspace": ASANA_WORKSPACE_GID, "projects": [ASANA_PROJECT_GID] } }
        
        result = tasks_api_instance.create_task(body=task_data_body, opts={})
        
        task_gid = result['gid']
        task_url = f"https://app.asana.com/0/{ASANA_PROJECT_GID}/{task_gid}"
        
        return AsanaExportResponse( message="Asanaタスクを正常に作成しました。", task_url=task_url )
    except ApiException as e:
        print(f"Asana API Error: {e.body}")
        raise HTTPException(status_code=500, detail=f"Asana APIエラーが発生しました。")
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Asanaへのエクスポート中に予期せぬエラーが発生しました: {str(e)}")

@app.get("/history", summary="分析履歴の一覧を取得")
async def get_history_list():
    try:
        history_summary = []
        files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
        for filename in files:
            file_path = os.path.join(HISTORY_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                reliability_data = data.get("reliability", {})
                score = reliability_data.get("score", 0.0) if isinstance(reliability_data, dict) else 0.0
                history_summary.append({ "id": data.get("id"), "createdAt": data.get("createdAt"), "originalFilename": data.get("originalFilename", "ファイル名不明"), "cost": data.get("cost", 0.0), "model_name": data.get("model_name", "不明"), "reliability_score": score })
        valid_history = [h for h in history_summary if h.get("createdAt")]
        sorted_history = sorted(valid_history, key=lambda x: x["createdAt"], reverse=True)
        return sorted_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"履歴の読み込み中にエラーが発生しました: {str(e)}")

@app.get("/history/{file_id}", summary="特定の分析履歴を取得")
async def get_history_detail(file_id: str):
    file_path = os.path.join(HISTORY_DIR, f"{file_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="指定された分析履歴が見つかりません。")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/history/delete", summary="指定された分析履歴を削除する")
async def delete_history(request: DeleteHistoryRequest):
    deleted_count = 0; errors = []
    for file_id in request.ids:
        if ".." in file_id or "/" in file_id or "\\" in file_id:
            errors.append(f"不正なID形式: {file_id}"); continue
        file_path = os.path.join(HISTORY_DIR, f"{file_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path); deleted_count += 1
            except Exception as e:
                errors.append(f"{file_id}の削除中にエラー: {e}")
        else:
            errors.append(f"ファイルが見つかりません: {file_id}")
    if errors:
        raise HTTPException(status_code=500, detail={"message": "一部のファイルの削除に失敗しました。", "errors": errors})
    return {"message": f"{deleted_count}件の履歴を削除しました。", "deleted_count": deleted_count}

@app.post("/benchmark-summary", summary="単一の音声ファイルで、複数のモデルの性能を比較する")
async def benchmark_summary_audio(file: UploadFile = File(...), models_to_benchmark: str = Form(...)):
    load_whisper_model()
    try: models_to_run = json.loads(models_to_benchmark)
    except Exception: raise HTTPException(status_code=400, detail="無効なモデルリストが送信されました。")
    original_filename, temp_file_path = file.filename, f"/tmp/{uuid.uuid4()}_{file.filename}"
    wav_file_path = f"{os.path.splitext(temp_file_path)[0]}.wav"
    try:
        with open(temp_file_path, "wb") as buffer: contents = await file.read(); buffer.write(contents)
        command = ["ffmpeg", "-i", temp_file_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_file_path]; subprocess.run(command, check=True, capture_output=True, text=True)
        audio = whisper.load_audio(wav_file_path)
        audio_duration_seconds = len(audio) / whisper.audio.SAMPLE_RATE
        transcription_result = whisper.transcribe(whisper_model, audio, language="ja", detect_disfluencies=True)
        transcript_text = transcription_result.get("text", "")
        cleaned_text = re.sub(r'[\(\[].*?[\)\]]', '', transcript_text or "").strip()
        if len(cleaned_text) < 10: raise HTTPException(status_code=400, detail="内容が短すぎるためベンチマークを実行できません。")
        benchmark_results = run_benchmark_pipeline(transcript_text, models_to_run)
        for result in benchmark_results:
            result["cost"] = calculate_cost_in_jpy(model_name=result["model_name"], total_input_tokens=result["token_usage"].get("input_tokens", 0), total_output_tokens=result["token_usage"].get("output_tokens", 0), audio_duration_seconds=audio_duration_seconds)
        return JSONResponse(content=benchmark_results)
    except Exception as e:
        print(traceback.format_exc()); raise HTTPException(status_code=500, detail=f"ベンチマーク中に予期せぬエラー: {str(e)}")
    finally:
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        if os.path.exists(wav_file_path): os.remove(wav_file_path)