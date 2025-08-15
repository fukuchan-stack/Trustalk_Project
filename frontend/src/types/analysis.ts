// frontend/src/types/analysis.ts

export interface AnalysisResult {
  id: string;
  originalFilename: string;
  model_name: string; // ★ この行を追加
  transcript: string;
  summary: string;
  todos: string[];
  speakers: string;
  cost: number;
  reliability: number;
}