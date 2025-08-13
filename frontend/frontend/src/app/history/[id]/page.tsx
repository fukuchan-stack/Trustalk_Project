'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';

// (型定義は変更なし)
interface HistoryLog {
  id: number;
  timestamp: string;
  model_name: string;
  question: string;
  generated_answer: string;
  ground_truth: string;
  faithfulness: number;
  final_judgement: string;
  cost_usd: number;
}

export default function HistoryDetailPage() {
  const params = useParams();
  const id = params.id;

  const [log, setLog] = useState<HistoryLog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      const fetchLogDetail = async () => {
        try {
          if (!process.env.NEXT_PUBLIC_API_URL) {
            throw new Error(".env.localにNEXT_PUBLIC_API_URLが設定されていません。");
          }
          const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/history/${id}`);
          if (!res.ok) {
            throw new Error('ログの取得に失敗しました。');
          }
          const data = await res.json();
          setLog(data);
        } catch (err) {
          if (err instanceof Error) {
            setError(err.message);
          } else {
            setError("不明なエラーが発生しました。");
          }
        } finally {
          setLoading(false);
        }
      };
      fetchLogDetail();
    }
  }, [id]);

  if (loading) return <div className="p-8">読み込み中...</div>;
  if (error) return <div className="p-8">エラー: {error}</div>;
  if (!log) return <div className="p-8">ログが見つかりません。</div>;

  return (
    <main className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <Link href="/" className="text-blue-600 hover:underline">
          &larr; ホームに戻る
        </Link>
      </div>
      <h1 className="text-3xl font-bold mb-6">分析結果詳細 (ID: {log.id})</h1>
      <div className="space-y-6">
        <div className="bg-white shadow-md rounded-lg p-6">
          <div className="flex justify-between items-start mb-3">
            <h2 className="text-2xl font-semibold">生成された要約</h2>
            <div className="flex space-x-4">
              <div className="text-right">
                <span className="font-bold text-lg text-gray-700">${log.cost_usd.toFixed(6)}</span>
                <p className="text-xs text-gray-500">概算コスト (USD)</p>
              </div>
              <div className="text-right">
                <span className={`font-bold text-lg ${log.final_judgement === 'O' ? 'text-green-600' : 'text-red-900'}`}>
                  {(log.faithfulness * 100).toFixed(1)}
                  <span className="text-sm font-normal text-gray-500"> / 100</span>
                </span>
                <p className="text-xs text-gray-500">信頼性スコア</p>
              </div>
            </div>
          </div>
          <div className="prose max-w-none whitespace-pre-wrap">{log.generated_answer}</div>
        </div>
        <div className="bg-white shadow-md rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-3">全体の文字起こし (原文)</h2>
          <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
            {log.ground_truth}
          </p>
        </div>
        <div className="bg-white shadow-md rounded-lg p-6 text-sm text-gray-600">
          <h3 className="text-lg font-semibold mb-3">メタデータ</h3>
          <ul>
            <li><strong>ファイル名:</strong> {log.question}</li>
            <li><strong>分析日時:</strong> {new Date(log.timestamp).toLocaleString('ja-JP')}</li>
            <li><strong>使用モデル:</strong> {log.model_name}</li>
          </ul>
        </div>
      </div>
    </main>
  );
}