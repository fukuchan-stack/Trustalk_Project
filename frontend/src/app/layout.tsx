// frontend/src/app/layout.tsx

import * as React from 'react';
import '@/styles/globals.css';

// メタデータ（ブラウザのタブに表示されるタイトルなど）
export const metadata = {
  title: 'Trustalk | AI音声ファイル分析',
  description: 'AIを活用した音声ファイル分析プラットフォーム',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html>
      <body>{children}</body>
    </html>
  );
}