"use client";

import { Download, RotateCcw } from "lucide-react";
import { getDownloadUrl } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

export function ResultPanel({ job, onReset }: { job: JobStatus; onReset: () => void }) {
  return (
    <section className="rounded border border-line bg-white p-5">
      <h2 className="text-xl font-semibold text-success">翻譯完成</h2>
      <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
        <p>輸出檔名：{job.output_filename}</p>
        <p>投影片總頁數：{job.total_slides}</p>
        <p>已處理文字的頁數：{job.stats.processed_text_slides}</p>
        <p>成功產生語音的頁數：{job.stats.generated_audio_slides}</p>
        <p>沒有講者備註的頁數：{job.stats.slides_without_notes}</p>
        <p>警告數量：{job.warnings.length}</p>
      </div>
      {job.warnings.length ? (
        <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
          {job.warnings.map((warning, index) => (
            <p key={`${index}-${warning}`}>{warning}</p>
          ))}
        </div>
      ) : null}
      <p className="mt-4 text-sm text-slate-600">檔案到期時間：{new Date(job.expires_at).toLocaleString()}</p>
      <div className="mt-5 flex flex-wrap gap-3">
        <a
          href={getDownloadUrl(job.job_id)}
          className="inline-flex items-center gap-2 rounded bg-brand px-4 py-2 font-semibold text-white hover:bg-blue-800"
        >
          <Download aria-hidden="true" className="h-5 w-5" />
          下載翻譯完成的簡報
        </a>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-2 rounded border border-line bg-white px-4 py-2 font-semibold hover:bg-mist"
        >
          <RotateCcw aria-hidden="true" className="h-5 w-5" />
          翻譯其他檔案
        </button>
      </div>
    </section>
  );
}
