"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import { cancelJob, createJob, getJob, getTranslationOptions, getTtsVoiceStatus } from "@/lib/api";
import type { JobStatus, LanguageCode, TranslationOption, TranslationProfile, TtsVoiceStatus } from "@/lib/types";
import { ErrorPanel } from "@/components/ErrorPanel";
import { LanguageSelect } from "@/components/LanguageSelect";
import { ProgressPanel } from "@/components/ProgressPanel";
import { ResultPanel } from "@/components/ResultPanel";
import { TranslationModelSelect } from "@/components/TranslationModelSelect";
import { UploadDropzone } from "@/components/UploadDropzone";
import { UsageNotes } from "@/components/UsageNotes";

const RETRY_INTERVAL_MS = 5000;

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState<LanguageCode>("zh-TW");
  const [targetLanguage, setTargetLanguage] = useState<LanguageCode>("en-US");
  const [translationProfile, setTranslationProfile] = useState<TranslationProfile>("local-primary");
  const [translationOptions, setTranslationOptions] = useState<TranslationOption[]>([]);
  const [loadingTranslationOptions, setLoadingTranslationOptions] = useState(true);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState<TtsVoiceStatus | null>(null);
  const [checkingVoice, setCheckingVoice] = useState(false);

  const locked = submitting || job?.state === "pending" || job?.state === "running";
  const selectedTranslationOption = translationOptions.find((option) => option.id === translationProfile);
  const translationReady = selectedTranslationOption?.available === true;
  const voiceReady = voiceStatus?.available === true;
  const canSubmit = useMemo(
    () => Boolean(file) && sourceLanguage !== targetLanguage && !locked && voiceReady && translationReady,
    [file, sourceLanguage, targetLanguage, locked, voiceReady, translationReady]
  );

  const loadTranslationOptions = useCallback(async () => {
    setLoadingTranslationOptions(true);
    try {
      const options = await getTranslationOptions();
      setTranslationOptions(options);
      if (!options.some((option) => option.id === translationProfile)) {
        setTranslationProfile(options[0]?.id ?? "local-primary");
      }
      setError(null);
      return true;
    } catch {
      setTranslationOptions((current) => current);
      return false;
    } finally {
      setLoadingTranslationOptions(false);
    }
  }, [translationProfile]);

  const checkVoiceStatus = useCallback(async (language: LanguageCode) => {
    setCheckingVoice(true);
    try {
      const status = await getTtsVoiceStatus(language);
      setVoiceStatus(status);
      return status.available;
    } catch {
      setVoiceStatus({
        provider: "sapi",
        language,
        available: true,
        voice_name: null,
        message: "尚未取得語音包狀態，系統會自動重試；送出時後端仍會再次檢查。"
      });
      return false;
    } finally {
      setCheckingVoice(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function loadUntilReady() {
      const ok = await loadTranslationOptions();
      if (!cancelled && !ok) {
        timer = window.setTimeout(loadUntilReady, RETRY_INTERVAL_MS);
      }
    }

    void loadUntilReady();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [loadTranslationOptions]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function checkUntilReady() {
      const ok = await checkVoiceStatus(targetLanguage);
      if (!cancelled && !ok && !locked) {
        timer = window.setTimeout(checkUntilReady, RETRY_INTERVAL_MS);
      }
    }

    void checkUntilReady();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [checkVoiceStatus, targetLanguage, locked]);

  useEffect(() => {
    if (!job || (job.state !== "pending" && job.state !== "running")) return;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await getJob(job.job_id);
        setJob(nextJob);
        if (nextJob.state === "canceled") {
          setCanceling(false);
          setError(nextJob.error_message ?? "翻譯已停止，未產生可下載檔案。");
        }
        if (nextJob.state === "failed") {
          setError(nextJob.error_message ?? "處理失敗，請重新上傳。");
        }
      } catch {
        // Ignore transient polling failures while the job is still running.
        // The next successful poll or backend job state will update the UI.
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  function reset() {
    setFile(null);
    setJob(null);
    setError(null);
    setSubmitting(false);
    setCanceling(false);
  }

  async function submit() {
    if (!file || !canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
      const created = await createJob(file, sourceLanguage, targetLanguage, translationProfile);
      setJob(created);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "無法建立翻譯工作。");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelCurrentJob() {
    if (!job || (job.state !== "pending" && job.state !== "running")) return;
    setCanceling(true);
    setError(null);
    try {
      const nextJob = await cancelJob(job.job_id);
      setJob(nextJob);
      if (nextJob.state === "canceled") {
        setCanceling(false);
        setError(nextJob.error_message ?? "翻譯已停止，未產生可下載檔案。");
      }
    } catch (cancelError) {
      setCanceling(false);
      setError(cancelError instanceof Error ? cancelError.message : "無法停止翻譯工作。");
    }
  }

  const voiceTone = voiceStatus?.available === false ? "danger" : voiceStatus?.voice_name ? "ready" : "unknown";

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#dff2ff_0,#f5f7fa_34rem)] px-5 py-8 text-ink">
      <div className="mx-auto max-w-6xl">
        <header className="mb-6">
          <p className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-white/80 px-3 py-1 text-sm font-semibold text-brand shadow-sm">
            <ShieldCheck aria-hidden="true" className="h-4 w-4" />
            公司內部簡報處理工具
          </p>
          <h1 className="mt-4 max-w-3xl text-3xl font-bold tracking-normal md:text-5xl">
            PowerPoint 翻譯與備註語音嵌入
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-700">
            上傳 .pptx 簡報，翻譯投影片文字與講者備註，並使用 Windows 語音包產生旁白。
          </p>
        </header>

        <section className="grid gap-5 lg:grid-cols-[1.35fr_0.65fr]">
          <div className="rounded border border-white/80 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">上傳簡報</h2>
                <p className="mt-1 text-sm text-slate-600">支援點選或拖曳上傳，系統一次只處理一個檔案。</p>
              </div>
              <span className="rounded bg-blue-50 px-3 py-1 text-sm font-medium text-brand">.pptx / 50 MB</span>
            </div>
            <UploadDropzone
              file={file}
              disabled={locked}
              onFileChange={(nextFile, validationError) => {
                setFile(nextFile);
                setError(validationError ?? null);
              }}
            />
          </div>

          <div className="grid gap-5">
            <section className="rounded border border-blue-100 bg-blue-50/60 p-5 shadow-sm">
              <h2 className="text-lg font-semibold">語言與語音</h2>
              <div className="mt-4">
                <LanguageSelect
                  disabled={locked}
                  sourceLanguage={sourceLanguage}
                  targetLanguage={targetLanguage}
                  onSourceChange={setSourceLanguage}
                  onTargetChange={setTargetLanguage}
                />
                <div className="mt-4">
                  <TranslationModelSelect
                    disabled={locked}
                    value={translationProfile}
                    options={translationOptions}
                    loading={loadingTranslationOptions}
                    onChange={setTranslationProfile}
                  />
                </div>
              </div>
              {sourceLanguage === targetLanguage ? (
                <p className="mt-3 text-sm font-medium text-danger">原始語言和目標語言不能相同。</p>
              ) : null}

              <section
                className={`mt-4 rounded border p-4 text-sm ${
                  voiceTone === "danger"
                    ? "border-red-200 bg-red-50 text-red-800"
                    : voiceTone === "ready"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                      : "border-blue-200 bg-white/80 text-blue-900"
                }`}
              >
                <div className="flex items-start gap-3">
                  {voiceTone === "danger" ? (
                    <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" />
                  ) : (
                    <CheckCircle2 aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">Windows 備註語音包狀態</p>
                    <p className="mt-1">
                      {checkingVoice
                        ? "正在檢查目標語言的 Windows 語音包..."
                        : voiceStatus?.message ?? "尚未取得語音包狀態，系統會自動重試。"}
                    </p>
                    {voiceStatus?.voice_name ? <p className="mt-1">偵測到語音：{voiceStatus.voice_name}</p> : null}
                    <button
                      type="button"
                      disabled={checkingVoice || locked}
                      onClick={() => void checkVoiceStatus(targetLanguage)}
                      className="mt-3 rounded border border-current px-3 py-1.5 text-xs font-semibold hover:bg-white/70 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      重新檢查語音包
                    </button>
                  </div>
                </div>
              </section>

              <button
                type="button"
                disabled={!canSubmit}
                onClick={submit}
                className="mt-5 inline-flex h-12 w-full items-center justify-center gap-2 rounded bg-brand px-5 font-semibold text-white shadow-sm hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                {locked ? <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" /> : null}
                {locked ? "翻譯中" : "開始翻譯"}
              </button>
              <p className="mt-3 text-sm text-slate-600">檔案完成或停止後保留 30 分鐘，請在期限內下載。</p>
            </section>
          </div>
        </section>

        <div className="mt-6 grid gap-5">
          {job && (job.state === "pending" || job.state === "running") ? (
            <ProgressPanel job={job} canceling={canceling} onCancel={cancelCurrentJob} />
          ) : null}
          {job?.state === "completed" ? <ResultPanel job={job} onReset={reset} /> : null}
          {error ? <ErrorPanel message={error} onReset={reset} /> : null}
        </div>

        <UsageNotes />
      </div>
    </main>
  );
}
