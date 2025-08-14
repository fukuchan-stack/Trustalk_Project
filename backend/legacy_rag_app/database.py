# database.py
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
import datetime

# SQLiteデータベースファイルのパス
DATABASE_URL = "sqlite:///evaluation_log.db"

# SQLAlchemyのエンジンを作成
# connect_argsはSQLite使用時にスレッドセーフを確保するために必要
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# データベースセッションを作成するためのクラス
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# モデルクラスのベースとなるクラス
Base = declarative_base()

class EvaluationLog(Base):
    """評価履歴を保存するためのデータベースモデル（テーブル）"""
    __tablename__ = "evaluation_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    model_name = Column(String, index=True)
    rag_config = Column(String)
    question = Column(String)
    ground_truth = Column(String)
    generated_answer = Column(String)
    retrieved_contexts = Column(String, default="")
    
    # 評価指標
    final_judgement = Column(String, index=True)
    tonic_score = Column(Float)
    cosine_similarity = Column(Float)
    mlflow_judgement = Column(String) # この名前は歴史的なものですが、LLMによる判定として残します
    faithfulness = Column(Float)
    answer_relevancy = Column(Float)
    context_precision = Column(Float)
    context_recall = Column(Float)

    # コスト
    cost_usd = Column(Float)

def init_db():
    """
    データベースを初期化し、テーブルが存在しない場合は作成します。
    アプリケーションの起動時に一度だけ呼び出されます。
    """
    Base.metadata.create_all(bind=engine)
