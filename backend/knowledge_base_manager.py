# sqlite3のバージョン問題を解決するためのパッチ
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import chromadb
import os
import openai
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import uuid

# このファイル自身の場所を基準に、絶対的なパスを構築する
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class KnowledgeBaseManager:
    """
    ミーティングのナレッジを管理するためのクラス。
    ベクトルデータベース(ChromaDB)への接続、データの追加、検索を担当します。
    """
    # BASE_DIRを基準にDBのパスを構築
    DB_PATH = os.path.join(BASE_DIR, "db", "chroma_db")
    COLLECTION_NAME = "meeting_transcripts"

    def __init__(self):
        """
        KnowledgeBaseManagerを初期化します。
        DBへの接続とコレクションの準備を行います。
        """
        os.makedirs(self.DB_PATH, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=self.DB_PATH)
        self.collection = self.client.get_or_create_collection(name=self.COLLECTION_NAME)
        
        if "OPENAI_API_KEY" not in os.environ:
            raise ValueError("環境変数 `OPENAI_API_KEY` が設定されていません。")
        openai.api_key = os.environ["OPENAI_API_KEY"]
        
        self.embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        
        print("✅ ナレッジベースの準備が完了しました。")
        print(f"データベースのパス: {os.path.abspath(self.DB_PATH)}")
        print(f"コレクション名: {self.collection.name}")
        print(f"現在のナレッジ数: {self.collection.count()}")

    def add_text_to_knowledge_base(self, text_content: str, metadata: dict):
        """
        与えられたテキストコンテンツをナレッジベースに追加します。
        """
        if not text_content.strip():
            print(f"⚠️  ソース: {metadata.get('source_file', '不明')} のコンテンツが空のため、スキップします。")
            return

        chunks = self.text_splitter.split_text(text_content)
        ids = [str(uuid.uuid4()) for _ in chunks]

        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=[metadata for _ in chunks]
        )
        
        print(f"✅ ソース: {metadata.get('source_file', '不明')} から {len(chunks)}個のナレッジを追加しました。")

    def search_knowledge_base(self, query_text: str, n_results: int = 5) -> list[str]:
        """
        ナレッジベースを検索し、クエリに関連性の高いドキュメントのリストを返します。
        """
        print(f"🔍 ナレッジベースを検索中... クエリ: '{query_text}'")
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # 'documents' の中の最初のリスト（クエリは1つなので）を返す
        retrieved_docs = results['documents'][0]
        print(f"✅ {len(retrieved_docs)}個の関連ドキュメントを取得しました。")
        return retrieved_docs
        
    def reset_database(self):
        """
        データベースのコレクションを一度削除し、再作成することで中身を空にします。
        """
        print("🗑️ データベースをリセットしています...")
        self.client.delete_collection(name=self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(name=self.COLLECTION_NAME)
        print("✅ データベースのリセットが完了しました。")

# このファイルが直接実行された場合のテスト用コード
if __name__ == '__main__':
    print("ナレッジベースマネージャーの初期化テストを開始します...")
    try:
        kb_manager = KnowledgeBaseManager()
        print("🎉 テスト成功: KnowledgeBaseManagerのインスタンスが正常に作成されました。")
    except Exception as e:
        print(f"❌ テスト失敗: 初期化中にエラーが発生しました。")
        print(e)