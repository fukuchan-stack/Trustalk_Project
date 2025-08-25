# Trustalk (トラストーク)

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/fukuchan-stack/Trustalk_Project)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Trustalkは、音声ファイル（会議の録音など）をアップロードするだけで、AIが自動的に文字起こし、要約、ToDoリストの抽出を行うWebアプリケーションです。**

過去の議事録内容はナレッジベースとして蓄積され、必要な情報をいつでもAIアシスタントに質問できます。忙しいビジネスパーソンの議事録作成コストを大幅に削減し、会議の内容を資産として活用することを目的としています。

---

### ✨ 主な機能

- **AIによる音声分析**:
  - `whisper-timestamped`による高精度な文字起こし
  - `pyannote.audio`による話者分離
  - 各種大規模言語モデル（GPT, Gemini, Claude）を活用した要約とToDoリストの自動生成
- **モデル性能比較**:
  - 同一の音声ファイルに対して複数のAIモデルを同時に実行し、性能（要約の質、コスト、処理時間）を比較・評価できます。
- **AIナレッジアシスタント**:
  - 過去に分析したすべての議事録をベクトルデータベースに保存。
  - 必要な情報をチャット形式でAIに質問し、関連する回答を即座に得られます。
- **Asana連携**:
  - 生成されたToDoリストを、ワンクリックでAsanaのタスクとして登録できます。
- **分析履歴の管理**:
  - 過去の分析結果を一覧で確認し、詳細な文字起こしや要約内容をいつでも閲覧・削除できます。

---

### 📸 スクリーンショット / デモ

<details>
<summary><strong>個別分析ページ</strong></summary>

![個別分析ページ1](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_1.1.png?raw=true)
![個別分析ページ2](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_1.2.png?raw=true)
![個別分析ページ3](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_1.3.png?raw=true)

</details>

<details>
<summary><strong>結果詳細ページ</strong></summary>

![結果詳細ページ1](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-result_1.1.png?raw=true)
![結果詳細ページ2](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-result_1.2.png?raw=true)
![結果詳細ページ3](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-result_1.3.png?raw=true)

</details>

<details>
<summary><strong>モデル性能比較ページ</strong></summary>

![モデル性能比較ページ1](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_2.1.png?raw=true)
![モデル性能比較ページ2](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_2.2.png?raw=true)
![モデル性能比較ページ3](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_2.3.png?raw=true)

</details>

<details>
<summary><strong>ナレッジ検索ページ</strong></summary>

![ナレッジ検索ページ1](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_3.1.png?raw=true)
![ナレッジ検索ページ2](https://github.com/fukuchan-stack/Trustalk_Project/blob/main/images/screenshot-main_3.2.png?raw=true)

</details>

---

### 🛠️ 使用技術

#### バックエンド
- **言語**: Python 3.11
- **フレームワーク**: FastAPI
- **AI / ML**:
  - **LLM連携**: LangChain, OpenAI API (GPT-4o mini, etc.), Google Gemini API, Anthropic Claude API
  - **文字起こし**: whisper-timestamped
  - **話者分離**: pyannote.audio
- **データベース**: ChromaDB (ベクトルデータベース)
- **サーバー**: Uvicorn

#### フロントエンド
- **言語**: TypeScript
- **フレームワーク**: Next.js (App Router)
- **UI**: React, Tailwind CSS
- **状態管理**: React Hooks (useState, useEffect)
- **グラフ描画**: Recharts

#### 開発環境・その他
- **コンテナ技術**: Docker, Devcontainer
- **開発環境**: GitHub Codespaces
- **バージョン管理**: Git / GitHub

---

### 🚀 セットアップと実行方法

このプロジェクトをローカル環境またはGitHub Codespacesで実行する手順です。

1.  **リポジトリをクローン**
    ```bash
    git clone [https://github.com/fukuchan-stack/Trustalk_Project.git](https://github.com/fukuchan-stack/Trustalk_Project.git)
    cd Trustalk_Project
    ```

2.  **環境変数の設定**
    プロジェクトの実行には、各種APIキーの設定が必要です。
    - **GitHub Codespacesで実行する場合**:
      リポジトリの `Settings > Secrets and variables > Codespaces` にAPIキーを設定してください。
    - **ローカル環境で実行する場合**:
      以下の内容で `.env` ファイルを `backend` ディレクトリに、`.env.local` ファイルを `frontend` ディレクトリにそれぞれ作成してください。
      **`backend/.env`**
      ```
      OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
      GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
      ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"
      HF_TOKEN="YOUR_HUGGING_FACE_TOKEN"
      ASANA_ACCESS_TOKEN="YOUR_ASANA_ACCESS_TOKEN"
      ```
      **`frontend/.env.local`**
      ```
      NEXT_PUBLIC_API_URL="[http://127.0.0.1:8000](http://127.0.0.1:8000)"
      ```

3.  **依存関係のインストール**
    **バックエンド**
    ```bash
    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install torch torchaudio --index-url [https://download.pytorch.org/whl/cpu](https://download.pytorch.org/whl/cpu)
    pip install -r requirements.txt
    ```
    **フロントエンド**
    ```bash
    cd frontend
    npm install
    ```

4.  **アプリケーションの起動**
    ターミナルを2つ開き、それぞれ以下のコマンドを実行します。
    - **ターミナル1 (バックエンド)**
      ```bash
      cd backend
      source .venv/bin/activate
      uvicorn main:app --host 0.0.0.0 --port 8000 --reload
      ```
    - **ターミナル2 (フロントエンド)**
      ```bash
      cd frontend
      npm run dev
      ```
    ブラウザで `http://localhost:3000` を開いてください。

---

### 📝 ライセンス

This project is licensed under the MIT License.

Copyright (c) 2025 fukuchan-stack