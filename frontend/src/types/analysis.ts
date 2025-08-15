// frontend/src/types/analysis.ts

export interface AnalysisResult {
  id: string;
  originalFilename: string;
  model_name: string;
  transcript: string;
  summary: string;
  todos: string[];
  speakers: string;
  cost: number;
  // ★ 変更点: reliabilityをオブジェクト型に変更
  reliability: {
    score: number;
    justification: string;
  };
}