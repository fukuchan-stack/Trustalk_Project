// frontend/src/app/page.tsx
'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

// 分析結果の型定義
interface AnalysisResult {
  filename: string;
  transcribed_text: string;
  summary: string;
  faithfulness_score: number;
  cost_usd: number;
}

// 履歴データの型定義
interface HistoryLog {
  id: number;
  timestamp: string;
  model_name: string;
  generated_answer: string;
  faithfulness: number;
  final_judgement: string;
  cost_usd: number;
}

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryLog[]>([]);

  // 履歴データをAPIから取得する関数
  const fetchHistory = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/history');
      if (!res.ok) {
        throw new Error('履歴の取得に失敗しました。');
      }
      const data = await res.json();
      setHistory(data);
    } catch (err: any) {
      console.error("履歴の取得エラー:", err.message);
    }
  };

  // ページが最初に読み込まれた時に履歴を取得する
  useEffect(() => {
    fetchHistory();
  }, []);

  // ファイルが選択されたときの処理
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  // アップロードボタンがクリックされたときの処理
  const handleUpload = async () => {
    if (!selectedFile) {
      alert('ファイルを選択してください。');
      return;
    }

    setIsUploading(true);
    setAnalysisResult(null); 
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error('アップロードに失敗しました。');
      }

      const data = await res.json();
      if (data.error) {
        throw new Error(data.error);
      }
      
      setAnalysisResult(data); 
      await fetchHistory();

    } catch (error: any) {
      setError(error.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main className="p-8 max-w-4xl mx-auto bg-red-200">
      <h1 className="text-3xl font-bold mb-6 text-center">Trustalk: 音声ファイル分析</h1>
      
      {/* 分析機能UI */}
      <div className="space-y-6 bg-white shadow-md rounded-lg p-6 mb-8">
        <div>
          <label htmlFor="audio-upload" className="block mb-2 font-medium text-gray-700">
            1. 音声ファイルを選択
          </label>
          <input 
            id="audio-upload"
            type="file" 
            onChange={handleFileChange}
            accept="audio/*"
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
        </div>
        <button 
          onClick={handleUpload}
          disabled={!selectedFile || isUploading}
          className="w-full px-6 py-3 bg-blue-600 text-white font-semibold rounded-md hover:bg-blue-700 disabled:bg-gray-400 transition-all duration-300"
        >
          {isUploading ? '分析中...' : '2. 分析を実行'}
        </button>
      </div>
      
      {/* エラー表示 */}
      {error && (
        <div className="mt-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
          <strong className="font-bold">エラー: </strong>
          <span className="block sm:inline">{error}</span>
        </div>
      )}

      {/* 最新の分析結果表示 */}
      {analysisResult && (
        <div className="mt-8 space-y-6">
          <div className="bg-white shadow-md rounded-lg p-6">
            <div className="flex justify-between items-start mb-3">
              <h2 className="text-2xl font-semibold">最新の分析結果</h2>
              <div className="flex space-x-4">
                <div className="text-right">
                  <span className="font-bold text-lg text-gray-700">${analysisResult.cost_usd.toFixed(6)}</span>
                  <p className="text-xs text-gray-500">概算コスト (USD)</p>
                </div>
                <div className="text-right">
                  <span className="font-bold text-lg text-green-600">
                    {(analysisResult.faithfulness_score * 100).toFixed(1)}
                    <span className="text-sm font-normal text-gray-500"> / 100</span>
                  </span>
                  <p className="text-xs text-gray-500">信頼性スコア</p>
                </div>
              </div>
            </div>
            <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: analysisResult.summary.replace(/\n/g, '<br />') }} />
          </div>
          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-3">全体の文字起こし</h2>
            <p className="text-gray-700 leading-relaxed">{analysisResult.transcribed_text}</p>
          </div>
        </div>
      )}

      {/* 分析履歴UI */}
      <div className="mt-12">
        <h2 className="text-2xl font-semibold mb-4">分析履歴</h2>
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <table className="min-w-full leading-normal">
            <thead>
              <tr>
                <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">ID</th>
                <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">日時</th>
                <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">要約</th>
                <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">信頼性</th>
                <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">コスト(USD)</th>
              </tr>
            </thead>
            <tbody>
              {history.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">
                    <Link href={`/history/${log.id}`} legacyBehavior>
                      <a className="text-blue-600 hover:underline cursor-pointer">{log.id}</a>
                    </Link>
                  </td>
                  <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">{new Date(log.timestamp).toLocaleString('ja-JP')}</td>
                  <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">
                    <p className="text-gray-900 whitespace-pre-wrap">{log.generated_answer.substring(0, 100)}...</p>
                  </td>
                  <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">
                    <span className={`relative inline-block px-3 py-1 font-semibold leading-tight ${log.final_judgement === 'O' ? 'text-green-900' : 'text-red-900'}`}>
                      <span aria-hidden className={`absolute inset-0 ${log.final_judgement === 'O' ? 'bg-green-200' : 'bg-red-200'} opacity-50 rounded-full`}></span>
                      <span className="relative">{(log.faithfulness * 100).toFixed(1)}</span>
                    </span>
                  </td>
                  <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">${log.cost_usd.toFixed(6)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}