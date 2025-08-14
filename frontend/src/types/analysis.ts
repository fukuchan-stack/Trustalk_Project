// frontend/src/types/analysis.ts

export interface AnalysisResult {
  id: string;
  transcript: string;
  summary: string;
  todos: string[];
  speakers: string;
  cost: number;
  reliability: number;
}