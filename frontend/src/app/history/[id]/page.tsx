// frontend/src/app/history/[id]/page.tsx

'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { AnalysisResult } from '@/types/analysis';

export default function HistoryDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    if (id && apiUrl) {
      const fetchLogDetail = async () => {
        try {
          setLoading(true);
          setError(null);
          const res = await fetch(`${apiUrl}/history/${id}`);
          if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.detail || '分析結果の取得に失敗しました。');
          }
          const data: AnalysisResult = await res.json();
          setResult(data);
        } catch (err: any) {
          setError(err.message || '不明なエラーが発生しました。');
        } finally {
          setLoading(false);
        }
      };
      fetchLogDetail();
    } else if (!apiUrl) {
        setError('APIのURLが設定されていません。');
        setLoading(false);
    }
  }, [id, apiUrl]);

  // ★ 修正点: データの読み込み中、エラー時、データが存在しない場合に、
  // このコンポーネントの処理をここで中断して、それぞれの表示を行う
  if (loading) {
    return (
        <div className="flex items-center justify-center min-h-screen">
            <div className="text-xl">読み込み中...</div>
        </div>
    );
  }
  
  if (error) {
    return (
        <div className="p-8 max-w-4xl mx-auto text-red-600">
            <h1 className="text-2xl font-bold mb-4">エラーが発生しました</h1>
            <p>{error}</p>
            <Link href="/" className="text-blue-600 hover:underline mt-4 inline-block">
                &larr; ホームに戻る
            </Link>
        </div>
    );
  }

  if (!result) {
    return (
        <div className="p-8 max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold mb-4">分析結果が見つかりません</h1>
             <Link href="/" className="text-blue-600 hover:underline mt-4 inline-block">
                &larr; ホームに戻る
            </Link>
        </div>
    );
  }

  // この行以降は、`result`がnullでないことが保証されている
  const todosText = result.todos && result.todos.length > 0
    ? result.todos.map(todo => `- ${todo}`).join('\n')
    : 'なし';

  return (
    <main className="bg-gray-50 min-h-screen p-4 sm:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <Link href="/" className="text-blue-600 hover:underline">
            &larr; ホームに戻る
          </Link>
        </div>
        
        <h1 className="text-3xl font-bold mb-2">分析結果</h1>
        <p className="text-gray-500 mb-6 text-xs">ID: {result.id}</p>
        
        <div className="space-y-6">
          {/* --- メタデータ --- */}
          <div className="bg-white shadow-md rounded-lg p-6 text-sm text-gray-600">
            <h3 className="text-lg font-semibold mb-3 text-gray-800">概要</h3>
            <ul>
              <li><strong>ファイル名:</strong> {result.originalFilename}</li>
              <li><strong>使用モデル:</strong> <span className="font-mono bg-gray-100 px-1 py-0.5 rounded">{result.model_name}</span></li>
            </ul>
          </div>
          
          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">AIによる要約</h2>
            <div className="prose max-w-none whitespace-pre-wrap">{result.summary}</div>
          </div>

          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">アクションアイテム (ToDo)</h2>
            <div className="prose max-w-none whitespace-pre-wrap">{todosText}</div>
          </div>

          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">話者ごとの発言</h2>
            <div className="prose max-w-none whitespace-pre-wrap bg-gray-100 p-4 rounded-md">{result.speakers}</div>
          </div>

          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">全体の文字起こし (原文)</h2>
            <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{result.transcript}</p>
          </div>
        </div>
      </div>
    </main>
  );
}