// frontend/src/app/page.tsx

"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface HistoryItem {
  id: string;
  createdAt: number;
  summary: string;
  originalFilename: string;
  cost: number;
  model_name: string;
  reliability_score: number;
}

const modelOptions = [
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini (高速・安価)' },
  { value: 'gemini-1.5-flash-latest', label: 'Gemini 1.5 Flash (高速・多機能)' },
  { value: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku (最速・最安価)' },
  { value: 'gpt-4o', label: 'GPT-4o (高性能)' },
  { value: 'gemini-1.5-pro-latest', label: 'Gemini 1.5 Pro (高性能・長時間対応)' },
  { value: 'claude-3-sonnet-20240229', label: 'Claude 3 Sonnet (バランス)' },
];

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedModel, setSelectedModel] = useState(modelOptions[0].value);
  const router = useRouter();
  
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchHistory = async () => {
    if (!apiUrl) return;
    try {
      const res = await fetch(`${apiUrl}/history`);
      if (!res.ok) throw new Error('履歴の取得に失敗しました。');
      const data: HistoryItem[] = await res.json();
      setHistory(data);
    } catch (err: any) {
      console.error("History fetch error:", err.message);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) setFile(event.target.files[0]);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) { setError('分析する音声ファイルを選択してください。'); return; }
    if (!apiUrl) { setError('APIのURLが設定されていません。'); return; }

    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model_name', selectedModel);

    try {
      const response = await fetch(`${apiUrl}/analyze`, { method: 'POST', body: formData });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'サーバーでエラーが発生しました。');
      }
      const data = await response.json();
      
      setSuccessMessage('分析が完了しました。結果ページに移動します...');
      setFile(null);
      if (document.getElementById('file-upload')) {
        (document.getElementById('file-upload') as HTMLInputElement).value = '';
      }

      setTimeout(() => {
        router.push(`/history/${data.id}`);
      }, 1500);

    } catch (err: any) {
      setError(err.message || '分析中に不明なエラーが発生しました。');
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-4 sm:p-8 bg-gray-50">
      <div className="w-full max-w-6xl">
        <div className="text-center mb-10">
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Trustalk</h1>
            <p className="text-lg text-gray-600">AIによる音声ファイル分析プラットフォーム</p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-md border border-gray-200 mb-12">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-2">1. 音声ファイルを選択</label>
              <input id="file-upload" type="file" onChange={handleFileChange} accept="audio/*" className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
            </div>
            <div>
              <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mb-2">2. AIモデルを選択</label>
              <select id="model-select" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md">
                {modelOptions.map((option) => ( <option key={option.value} value={option.value}>{option.label}</option> ))}
              </select>
            </div>
            <button type="submit" disabled={isLoading || !file} className="w-full bg-blue-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-300">
              {isLoading ? '分析中...' : '3. 分析を開始'}
            </button>
          </form>
          {error && ( <div className="mt-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg"><p className="font-bold">エラー</p><p>{error}</p></div> )}
          {successMessage && ( <div className="mt-6 p-4 bg-green-100 border border-green-400 text-green-700 rounded-lg"><p className="font-bold">成功</p><p>{successMessage}</p></div> )}
        </div>
        
        <div>
          <h2 className="text-2xl font-bold text-gray-800 mb-4">分析履歴</h2>
          <div className="bg-white shadow-md rounded-lg overflow-hidden">
            <table className="min-w-full leading-normal">
              <thead>
                <tr>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider w-12">No.</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">分析日時</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">ファイル名</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">使用モデル</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">信頼性</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">コスト (円)</th>
                </tr>
              </thead>
              <tbody>
                {history.length > 0 ? (
                  history.map((item, index) => (
                    <tr key={item.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => router.push(`/history/${item.id}`)}>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm"><p className="text-blue-600 hover:text-blue-800 whitespace-no-wrap font-semibold">{index + 1}</p></td>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm"><p className="text-gray-900 whitespace-no-wrap">{new Date(item.createdAt * 1000).toLocaleString('ja-JP')}</p></td>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm"><p className="text-gray-900 whitespace-no-wrap">{item.originalFilename}</p></td>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm"><span className="font-mono bg-gray-100 text-gray-700 px-2 py-1 rounded-md text-xs">{item.model_name}</span></td>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm text-right"><span className={`font-semibold ${ item.reliability_score > 0.8 ? 'text-green-600' : item.reliability_score > 0.6 ? 'text-yellow-600' : 'text-red-600' }`}>{(item.reliability_score * 100).toFixed(0)}</span><span className="text-gray-500 text-xs"> / 100</span></td>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm text-right">
                        <p className="text-gray-600 whitespace-no-wrap">{item.cost.toFixed(3)} 円</p>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={6} className="px-5 py-5 border-b border-gray-200 bg-white text-sm text-center text-gray-500">分析履歴はまだありません。</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}