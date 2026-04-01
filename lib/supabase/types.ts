export type ProjectStatus = "draft" | "completed";
export type WorkflowMode = "hybrid" | "full-ai";

export interface Project {
  id: string;
  user_id: string;
  name: string;
  status: ProjectStatus;
  job_id: string | null;
  step: number;
  workflow_mode: WorkflowMode | null;
  transcript: string;
  polished_transcript: string;
  outline: any | null;
  polished_outline: any | null;
  timing_map: any[];
  settings: ProjectSettings;
  slide_count: number;
  video_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSettings {
  audioSettings?: {
    cleanupEnabled: boolean;
    cleanupMode: "strict" | "natural";
    silenceThreshold: number;
    speedFactor: number;
  };
  slideSettings?: {
    mode: "auto" | "fewer" | "more" | "custom";
    customCount: number;
  };
  selectedColorTheme?: string;
  selectedFontStyle?: string;
  designPreference?: string;
  textDensity?: "simple" | "standard";
  aspectRatio?: "landscape" | "portrait";
  bgmEnabled?: boolean;
  bgmVolume?: number;
  bgmPlayMode?: "loop" | "single" | "minute";
  bgmFadeIn?: boolean;
  bgmFadeOut?: boolean;
  addIllustrations?: boolean;
  illustrationPercentage?: number;
  illustrationRequest?: string;
}

export interface UserSettings {
  id: string;
  user_id: string;
  openai_key: string;
  gemini_key: string;
  gemini_model: string;
  openrouter_key?: string;
  openrouter_model?: string;
  openrouter_design_model?: string;
  created_at: string;
  updated_at: string;
}
