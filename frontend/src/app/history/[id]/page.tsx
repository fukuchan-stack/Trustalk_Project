'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { AnalysisResult } from '@/types/analysis';
import { SpeakerPieChart } from '@/components/charts/SpeakerPieChart';
// ★ 1. ボタン用のアイコンをインポート
import { Send, Check, Loader2 } from 'lucide-react';

interface SpeakerContributionData {
  name: string;
  value: number;
}

// ★ 2. 各ToDoのエクスポート状態を管理するための型
type ExportStatus = 'idle' | 'loading' | 'success' | 'error';

export default function HistoryDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [dashboardData, setDashboardData] = useState<SpeakerContributionData[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // ★ 2. 各ToDoのエクスポート状態を管理するstateを追加 (キーはToDoのインデックス番号)
  const [exportStatus, setExportStatus] = useState<Record<number, ExportStatus>>({});

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    if (id && apiUrl) {
      const fetchDetails = async () => {
        try {
          setLoading(true);
          setError(null);
          
          const [resultRes, dashboardRes] = await Promise.all([
            fetch(`${apiUrl}/history/${id}`),
            fetch(`${apiUrl}/api/dashboard/${id}`)
          ]);

          if (!resultRes.ok) {
            const errorData = await resultRes.json();
            throw new Error(errorData.detail || '分析結果の取得に失敗しました。');
          }
          if (!dashboardRes.ok) {
            console.error("ダッシュボードデータの取得に失敗しました。");
          }

          const resultData: AnalysisResult = await resultRes.json();
          setResult(resultData);

          if (dashboardRes.ok) {
            const dashboardJson = await dashboardRes.json();
            setDashboardData(dashboardJson.speaker_contributions);
          }

        } catch (err: any) {
          setError(err.message || '不明なエラーが発生しました。');
        } finally {
          setLoading(false);
        }
      };
      fetchDetails();
    } else if (!apiUrl) {
        setError('APIのURLが設定されていません。');
        setLoading(false);
    }
  }, [id, apiUrl]);

  // ★ 3. Asana連携ロジックを実装
  const handleExportToAsana = async (todoText: string, index: number) => {
    if (!apiUrl) {
      alert('エラー: APIのURLが設定されていません。');
      return;
    }
    
    // 特定のToDoのステータスを'loading'に更新
    setExportStatus(prev => ({ ...prev, [index]: 'loading' }));
    
    try {
      const response = await fetch(`${apiUrl}/api/export/asana`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_name: todoText, notes: `"${result?.originalFilename}"の議事録から作成されました。` }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Asanaへのエクスポートに失敗しました。');
      }

      const data = await response.json();
      setExportStatus(prev => ({ ...prev, [index]: 'success' }));
      // 成功したら、新しいタブでAsanaタスクを開く
      window.open(data.task_url, '_blank');

    } catch (err: any) {
      setExportStatus(prev => ({ ...prev, [index]: 'error' }));
      alert(`エラー: ${err.message}`);
      // 一定時間後にステータスを元に戻す
      setTimeout(() => setExportStatus(prev => ({ ...prev, [index]: 'idle' })), 3000);
    }
  };


  if (loading) {
    return ( <div className="flex items-center justify-center min-h-screen"><div className="text-xl">読み込み中...</div></div> );
  }
  
  if (error) {
    return ( <div className="p-8 max-w-4xl mx-auto text-red-600"><h1 className="text-2xl font-bold mb-4">エラーが発生しました</h1><p>{error}</p><Link href="/" className="text-blue-600 hover:underline mt-4 inline-block">&larr; ホームに戻る</Link></div> );
  }

  if (!result) {
    return ( <div className="p-8 max-w-4xl mx-auto"><h1 className="text-2xl font-bold mb-4">分析結果が見つかりません</h1><Link href="/" className="text-blue-600 hover:underline mt-4 inline-block">&larr; ホームに戻る</Link></div> );
  }
    
  const reliabilityScore = Math.round(result.reliability.score * 100);
  const scoreColor = reliabilityScore > 80 ? 'text-green-600' : reliabilityScore > 60 ? 'text-yellow-600' : 'text-red-600';

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
          <div className="bg-white shadow-md rounded-lg p-6 text-sm text-gray-600">
            <h3 className="text-lg font-semibold mb-3 text-gray-800">概要</h3>
            <ul>
              <li><strong>ファイル名:</strong> {result.originalFilename}</li>
              <li><strong>使用モデル:</strong> <span className="font-mono bg-gray-100 px-1 py-0.5 rounded">{result.model_name}</span></li>
              <li><strong>概算コスト:</strong> {result.cost.toFixed(3)} 円</li>
            </ul>
          </div>
          
          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">信頼性スコア</h2>
            <div className="flex items-center space-x-4">
              <div className={`text-5xl font-bold ${scoreColor}`}>
                {reliabilityScore}
                <span className="text-2xl text-gray-500">/ 100</span>
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-800">評価AIのコメント</h3>
                <p className="text-gray-600 italic">"{result.reliability.justification}"</p>
              </div>
            </div>
          </div>

          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">分析ダッシュボード</h2>
            {dashboardData ? (
                <div className='w-full h-72'>
                    <h3 className="font-semibold text-gray-800 text-center mb-2">話者ごとの発言量</h3>
                    <SpeakerPieChart data={dashboardData} />
                </div>
            ) : (
                <p className="text-center text-gray-500">ダッシュボードデータを読み込み中...</p>
            )}
          </div>

          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">AIによる要約</h2>
            <div className="prose max-w-none whitespace-pre-wrap">{result.summary}</div>
          </div>

          {/* ★ 4. ToDoリストのUIを変更 */}
          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">アクションアイテム (ToDo)</h2>
            {result.todos && result.todos.length > 0 ? (
                <ul className="space-y-4">
                  {result.todos.map((todo, index) => {
                    const status = exportStatus[index] || 'idle';
                    return (
                      <li key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <span className="text-gray-800 flex-grow">{todo}</span>
                        <button 
                          onClick={() => handleExportToAsana(todo, index)}
                          disabled={status === 'loading' || status === 'success'}
                          className={`ml-4 px-3 py-1 text-xs font-semibold text-white rounded-full flex items-center transition-all duration-300
                            ${status === 'idle' ? 'bg-blue-500 hover:bg-blue-600' : ''}
                            ${status === 'loading' ? 'bg-gray-400 cursor-not-allowed' : ''}
                            ${status === 'success' ? 'bg-green-500' : ''}
                            ${status === 'error' ? 'bg-red-500 hover:bg-red-600' : ''}
                          `}
                        >
                          {status === 'idle' && <><Send className="mr-1 h-3 w-3" /> Asanaへ</>}
                          {status === 'loading' && <><Loader2 className="mr-1 h-3 w-3 animate-spin" /> 送信中</>}
                          {status === 'success' && <><Check className="mr-1 h-3 w-3" /> 送信済み</>}
                          {status === 'error' && <>再試行</>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-gray-500">なし</p>
            )}
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