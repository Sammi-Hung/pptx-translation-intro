"use client";

import { Loader2, Square } from "lucide-react";
import type { JobStatus } from "@/lib/types";

export function ProgressPanel({
  job,
  canceling,
  onCancel
}: {
  job: JobStatus;
  canceling: boolean;
  onCancel: () => void;
}) {
  const isCanceling = canceling || job.cancel_requested;

  return (
    <section className="rounded border border-line bg-white p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">翻譯中</h2>
          <p className="text-sm text-slate-600">{job.stage}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isCanceling}
            onClick={onCancel}
            className="inline-flex h-10 items-center gap-2 rounded border border-red-200 bg-red-50 px-3 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isCanceling ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : (
              <Square aria-hidden="true" className="h-4 w-4" />
            )}
            {isCanceling ? "停止中" : "停止翻譯"}
          </button>
          <Loader2 aria-hidden="true" className="h-6 w-6 animate-spin text-brand" />
        </div>
      </div>
      <div className="mt-5 h-3 overflow-hidden rounded bg-slate-200">
        <div className="h-full rounded bg-brand transition-all" style={{ width: `${job.progress_percent}%` }} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-semibold">{job.progress_percent}%</span>
        <span>
          第 {job.current_slide || 0}/{job.total_slides || 0} 頁
        </span>
      </div>
      <p className="mt-4 rounded bg-mist px-3 py-2 text-sm">
        {isCanceling ? "正在停止翻譯，請稍候。" : job.message}
      </p>
    </section>
  );
}
