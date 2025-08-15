# backend/main.py (履歴APIを改良した最終確定版)

import os
import uuid
import json
import torch
import traceback
import subprocess
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pyannote.audio import Pipeline
import whisper_timestamped as whisper

# --- 環境変数とクライアントの初期化 ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
if not OPENAI_API_KEY or not HF_TOKEN:
    raise ValueError("APIキーまたはトークンが設定されていません。GitHub Secretsを確認してください。")
client = OpenAI(api_key=OPENAI_API_KEY)

# --- AIモデルの初期化 ---
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")
try:
    print("Whisper: Loading 'base' model...")
    whisper_model = whisper.load_model("base", device=device)
    print("Whisper: Model loaded successfully.")
except Exception as e:
    print(f"Whisper: モデルの読み込みに失敗しました。Error: {e}")
    whisper_model = None
try:
    print("Pyannote: Loading diarization pipeline...")
    diarization_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", use_auth_token=HF_TOKEN
    ).to(torch.device(device))
    print("Pyannote: Diarization pipeline loaded successfully.")
except Exception as e:
    print(f"Pyannote: Pipelineの読み込みに失敗しました。Error: {e}")
    diarization_pipeline = None

# --- FastAPIアプリケーションのセットアップ ---
app = FastAPI(title="Trustalk API", version="1.5.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https?://.*\.github\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# --- ヘルパー関数 ---
def merge_results(diarization, transcription):
    if not diarization: return "話者分離パイプラインが利用できません。", transcription.get("text", "")
    word_speakers = []
    for segment in transcription.get("segments", []):
        for word in segment.get("words", []):
            word_start, word_end = word.get('start', 0), word.get('end', 0)
            speaker_label = "UNKNOWN"
            try:
                cropped_annotation = diarization.crop(word)
                if cropped_annotation:
                    speaker_turn = cropped_annotation.get_timeline().support().pop(0)
                    speaker_label = speaker_turn[2]
            except (IndexError, KeyError): speaker_label = "UNKNOWN"
            word_speakers.append({'word': word.get('text', ''), 'speaker': speaker_label})
    if not word_speakers: return "発言が見つかりませんでした。", transcription.get("text", "")
    full_transcript_with_speakers = ""
    current_speaker = word_speakers[0]['speaker']
    current_speech = ""
    for item in word_speakers:
        word = item['word']
        speaker = item['speaker']
        if speaker != current_speaker:
            full_transcript_with_speakers += f"**{current_speaker}**: {current_speech.strip()}\n\n"
            current_speech = ""
        current_speech += word + " "
        current_speaker = speaker
    if current_speech: full_transcript_with_speakers += f"**{current_speaker}**: {current_speech.strip()}\n"
    return full_transcript_with_speakers.strip(), transcription.get("text", "")

# --- APIエンドポイント ---
@app.get("/", summary="APIのヘルスチェック")
def read_root(): return {"status": "ok", "message": "Welcome to Trustalk API!"}

@app.post("/analyze", summary="音声ファイルの分析")
async def analyze_audio(file: UploadFile = File(...)):
    if whisper_model is None or diarization_pipeline is None:
        raise HTTPException(status_code=503, detail="AIモデルが利用できません。サーバーのログを確認してください。")
    
    original_filename = file.filename
    temp_file_path = f"/tmp/{uuid.uuid4()}_{original_filename}"
    wav_file_path = f"{os.path.splitext(temp_file_path)[0]}.wav"
    try:
        with open(temp_file_path, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)
        
        print(f"Converting {temp_file_path} to WAV format...")
        command = ["ffmpeg", "-i", temp_file_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_file_path]
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("Conversion to WAV successful.")

        print("Whisper: Starting timestamped transcription...")
        audio = whisper.load_audio(wav_file_path)
        transcription_result = whisper.transcribe(whisper_model, audio, language="ja", detect_disfluencies=True)
        print("Whisper: Transcription finished.")
        
        print("Pyannote: Starting diarization...")
        diarization_result = diarization_pipeline(wav_file_path)
        print("Pyannote: Diarization finished.")

        print("Merging results...")
        speakers_text, transcript_text = merge_results(diarization_result, transcription_result)
        print("Merging finished.")
        
        print("LLM: Generating summary and ToDos...")
        system_prompt = "あなたは、会議の文字起こしを分析し、要点とアクションアイテムを抽出する優秀なアシスタントです。"
        human_prompt = f"""以下の会議の文字起こしを読んでください。

# 文字起こし
{transcript_text}

# 命令
1. この会議の要約を3〜5個の箇条書きで作成してください。
2. この会議で発生したToDo（アクションアイテム）を「誰が・何を・いつまでに行うか」が分かるようにリストアップしてください。ToDoがない場合は「なし」と記述してください。

あなたの回答は、以下のJSON形式で返してください。キーの変更や追加はしないでください。
{{
  "summary": [
    "要約の箇条書き1",
    "要約の箇条書き2"
  ],
  "todos": [
    "【担当者A】タスク内容A（期日：YYYY-MM-DD）",
    "【担当者B】タスク内容B（期日：不明）"
  ]
}}
"""
        response = client.chat.completions.create(model="gpt-4o-mini", response_format={"type": "json_object"}, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": human_prompt}])
        llm_result_str = response.choices[0].message.content
        llm_result = json.loads(llm_result_str)
        print("LLM: Generation finished.")

        result = { 
            "id": str(uuid.uuid4()),
            "originalFilename": original_filename,
            "transcript": transcript_text, 
            "summary": "\n".join(f"- {item}" for item in llm_result.get("summary", [])), 
            "todos": llm_result.get("todos", []), 
            "speakers": speakers_text, 
            "cost": 0.0, 
            "reliability": 0.0 
        }

        history_file_path = os.path.join(HISTORY_DIR, f"{result['id']}.json")
        with open(history_file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        return JSONResponse(content=result)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg error: {e.stderr}")
        raise HTTPException(status_code=400, detail=f"サポートされていない音声ファイル形式です。ffmpegエラー: {e.stderr}")
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"分析中に予期せぬエラーが発生しました: {str(e)}")
    finally:
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        if os.path.exists(wav_file_path): os.remove(wav_file_path)

@app.get("/history", summary="分析履歴の一覧を取得")
async def get_history_list():
    """保存されているすべての分析履歴の要約情報を、更新日時が新しい順に返す"""
    try:
        history_summary = []
        files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
        
        for filename in files:
            file_path = os.path.join(HISTORY_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # historyフォルダ内の各JSONファイルから要約情報を抽出
                history_summary.append({
                    "id": data.get("id"),
                    "createdAt": os.path.getmtime(file_path), # ファイルの更新日時をタイムスタンプとして使用
                    "summary": data.get("summary", "要約なし").split('\n')[0], # 要約の1行目だけを取得
                    "originalFilename": data.get("originalFilename", "ファイル名不明"),
                    "cost": data.get("cost", 0.0) # コスト情報を追加
                })
        
        # 作成日時が新しい順にソート
        sorted_history = sorted(history_summary, key=lambda x: x["createdAt"], reverse=True)
        return sorted_history
    except Exception as e:
        print(traceback.format_exc())
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