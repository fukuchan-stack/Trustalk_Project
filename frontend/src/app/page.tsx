'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFile(event.target.files[0]);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError('分析する音声ファイルを選択してください。');
      return;
    }

    setIsLoading(true);
    setError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      // フロントエンドは自身のBFF (/api/analyze) にリクエストを送信
      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        // バックエンドやBFFからのエラーメッセージを取得して表示
        const errorText = await response.text();
        throw new Error(errorText || 'サーバーでエラーが発生しました。');
      }

      const data = await response.json();
      
      // 分析成功後、結果表示ページにリダイレクト
      router.push(`/history/${data.id}`);

    } catch (err: any) {
      setError(err.message || '分析中に不明なエラーが発生しました。');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-gray-50">
      <div className="w-full max-w-2xl text-center">
        <h1 className="text-4xl font-bold text-gray-800 mb-2">Trustalk</h1>
        <p className="text-lg text-gray-600 mb-8">AIによる音声ファイル分析プラットフォーム</p>

        <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md border border-gray-200">
          <div className="mb-6">
            <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-2">
              音声ファイルを選択 (mp3, wav, m4aなど)
            </label>
            <input
              id="file-upload"
              type="file"
              onChange={handleFileChange}
              accept="audio/*"
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-full file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || !file}
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
      </div>
    </main>
  );
}