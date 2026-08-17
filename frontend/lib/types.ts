export type LanguageCode = "zh-TW" | "en-US" | "th-TH";
export type TranslationProfile = "cloud" | "local-primary" | "local-secondary";

export type JobState = "pending" | "running" | "completed" | "failed" | "canceled" | "expired";

export interface JobStatus {
  job_id: string;
  original_filename: string;
  output_filename: string | null;
  source_language: LanguageCode;
  target_language: LanguageCode;
  translation_profile: TranslationProfile;
  translation_provider: string | null;
  translation_model: string | null;
  state: JobState;
  progress_percent: number;
  stage: string;
  current_slide: number;
  total_slides: number;
  message: string;
  created_at: string;
  completed_at: string | null;
  expires_at: string;
  warnings: string[];
  error_code: string | null;
  error_message: string | null;
  cancel_requested: boolean;
  output_validated: boolean;
  stats: {
    processed_text_slides: number;
    generated_audio_slides: number;
    slides_without_notes: number;
    required_audio_slides: number[];
  };
}

export interface TtsVoiceStatus {
  provider: string;
  language: LanguageCode;
  available: boolean;
  voice_name: string | null;
  message: string;
}

export interface TranslationOption {
  id: TranslationProfile;
  label: string;
  provider: string;
  model: string | null;
  api_url: string | null;
  available: boolean;
}

export const languages: Array<{ code: LanguageCode; label: string }> = [
  { code: "zh-TW", label: "繁體中文" },
  { code: "en-US", label: "英文" },
  { code: "th-TH", label: "泰文" }
];
