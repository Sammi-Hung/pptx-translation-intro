import type { JobStatus, LanguageCode, TranslationOption, TranslationProfile, TtsVoiceStatus } from "./types";

const VOICE_STATUS_TIMEOUT_MS = 5000;

function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configured && configured !== "auto") return configured.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    if (window.location.hostname === "localhost") {
      return "http://127.0.0.1:8000";
    }
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

function readApiError(error: unknown): string {
  if (typeof error === "object" && error && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "伺服器暫時無法回應，請稍後再試。";
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }
  const payload = await response.json().catch(() => null);
  const detail = payload?.detail;
  throw new Error(readApiError(detail));
}

export async function createJob(
  file: File,
  sourceLanguage: LanguageCode,
  targetLanguage: LanguageCode,
  translationProfile: TranslationProfile
): Promise<JobStatus> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source_language", sourceLanguage);
  formData.append("target_language", targetLanguage);
  formData.append("translation_profile", translationProfile);
  const response = await fetch(`${getApiBaseUrl()}/api/jobs`, {
    method: "POST",
    body: formData
  });
  return parseResponse<JobStatus>(response);
}

export async function getTranslationOptions(): Promise<TranslationOption[]> {
  const response = await fetch(`${getApiBaseUrl()}/api/translation/options`, { cache: "no-store" });
  const payload = await parseResponse<{ options: TranslationOption[] }>(response);
  return payload.options;
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${getApiBaseUrl()}/api/jobs/${jobId}`, { cache: "no-store" });
  return parseResponse<JobStatus>(response);
}

export async function cancelJob(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${getApiBaseUrl()}/api/jobs/${jobId}/cancel`, {
    method: "POST",
    cache: "no-store"
  });
  return parseResponse<JobStatus>(response);
}

export async function getTtsVoiceStatus(language: LanguageCode): Promise<TtsVoiceStatus> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), VOICE_STATUS_TIMEOUT_MS);
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tts/voices/${language}`, {
      cache: "no-store",
      signal: controller.signal
    });
    return parseResponse<TtsVoiceStatus>(response);
  } finally {
    window.clearTimeout(timeout);
  }
}

export function getDownloadUrl(jobId: string): string {
  return `${getApiBaseUrl()}/api/jobs/${jobId}/download`;
}
