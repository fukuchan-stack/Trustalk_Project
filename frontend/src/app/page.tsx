// frontend/src/app/page.tsx (UI/UX改善版)

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

// 履歴一覧のアイテムの型を定義
interface HistoryItem {
  id: string;
  createdAt: number;
  summary: string;
  originalFilename: string;
}

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const router = useRouter();
  
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  // 履歴を取得する関数
  const fetchHistory = async () => {
    if (!apiUrl) return;
    try {
      const res = await fetch(`${apiUrl}/history`);
      if (!res.ok) {
        throw new Error('履歴の取得に失敗しました。');
      }
      const data: HistoryItem[] = await res.json();
      setHistory(data);
    } catch (err: any) {
      console.error("History fetch error:", err.message);
    }
  };

  // ページが読み込まれた時に履歴を取得
  useEffect(() => {
    fetchHistory();
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFile(event.target.files[0]);
    }
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

    try {
      const response = await fetch(`${apiUrl}/analyze`, { method: 'POST', body: formData });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'サーバーでエラーが発生しました。');
      }
      
      setSuccessMessage('分析が完了しました。履歴が更新されます。');
      setFile(null);
      (document.getElementById('file-upload') as HTMLInputElement).value = '';
      await fetchHistory();

    } catch (err: any) {
      setError(err.message || '分析中に不明なエラーが発生しました。');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-4 sm:p-8 bg-gray-50">
      <div className="w-full max-w-4xl">
        <div className="text-center mb-10">
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Trustalk</h1>
            <p className="text-lg text-gray-600">AIによる音声ファイル分析プラットフォーム</p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-md border border-gray-200 mb-12">
          <form onSubmit={handleSubmit}>
            <div className="mb-6">
              <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-2">
                音声ファイルを選択 (mp3, m4a, wavなど)
              </label>
              <input id="file-upload" type="file" onChange={handleFileChange} accept="audio/*"
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>
            <button type="submit" disabled={isLoading || !file}
              className="w-full bg-blue-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-300"
            >
              {isLoading ? '分析中...' : '分析を開始'}
            </button>
          </form>
          {error && (
            <div className="mt-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
              <p className="font-bold">エラー</p>
              <p>{error}</p>
            </div>
          )}
          {successMessage && (
            <div className="mt-6 p-4 bg-green-100 border border-green-400 text-green-700 rounded-lg">
              <p className="font-bold">成功</p>
              <p>{successMessage}</p>
            </div>
          )}
        </div>
        
        <div>
          <h2 className="text-2xl font-bold text-gray-800 mb-4">分析履歴</h2>
          <div className="bg-white shadow-md rounded-lg overflow-hidden">
            <table className="min-w-full leading-normal">
              <thead>
                <tr>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider w-16">No.</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">分析日時</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">ファイル名</th>
                  <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">要約（冒頭）</th>
                </tr>
              </thead>
              <tbody>
                {history.length > 0 ? (
                  history.map((item, index) => (
                    <tr key={item.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => router.push(`/history/${item.id}`)}>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm">
                        <p className="text-blue-600 hover:text-blue-800 underline whitespace-no-wrap font-semibold">
                          {index + 1}
                        </p>
                      </td>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm">
                        <p className="text-gray-900 whitespace-no-wrap">
                          {new Date(item.createdAt * 1000).toLocaleString('ja-JP')}
                        </p>
                      </td>
                       <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm">
                        <p className="text-gray-900 whitespace-no-wrap">{item.originalFilename}</p>
                      </td>
                      <td className="px-5 py-4 border-b border-gray-200 bg-white text-sm">
                        <p className="text-gray-900 whitespace-no-wrap">{item.summary}</p>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="px-5 py-5 border-b border-gray-200 bg-white text-sm text-center text-gray-500">
                      分析履歴はまだありません。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}