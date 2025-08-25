"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

// グラフのデータ一件一件の型を定義
interface ChartData {
  name: string;
  value: number;
}

// このコンポーネントが受け取るプロパティ（props）の型を定義
interface SpeakerPieChartProps {
  data: ChartData[];
}

// 円グラフの各セクションの色を定義
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#AF19FF', '#FF1943'];

export function SpeakerPieChart({ data }: SpeakerPieChartProps) {
  // データがない場合は何も表示しない
  if (!data || data.length === 0) {
    return <div className="text-center text-gray-500">発言データがありません。</div>;
  }

  return (
    // レスポンシブ対応のコンテナでグラフ全体を囲む
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%" // 中央（X軸）
          cy="50%" // 中央（Y軸）
          labelLine={false}
          // ★★★ 修正点: percentがundefinedの場合に備えて0に置き換える処理を追加 ★★★
          label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
          outerRadius={80} // 円の大きさ
          fill="#8884d8"
          dataKey="value" // データのどの値を円の割合に使うかを指定
        >
          {/* データの数だけCell（円のセクション）を描画 */}
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        {/* マウスをホバーした時に表示されるツールチップ */}
        <Tooltip formatter={(value: number) => [`${value} 文字`, "発言文字数"]} />
      </PieChart>
    </ResponsiveContainer>
  );
}