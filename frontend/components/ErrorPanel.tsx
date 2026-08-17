"use client";

import { RotateCcw, TriangleAlert } from "lucide-react";

export function ErrorPanel({ message, onReset }: { message: string; onReset: () => void }) {
  return (
    <section className="rounded border border-red-200 bg-red-50 p-5">
      <div className="flex items-start gap-3">
        <TriangleAlert aria-hidden="true" className="mt-1 h-6 w-6 text-danger" />
        <div>
          <h2 className="text-lg font-semibold text-danger">處理失敗</h2>
          <p className="mt-1 text-sm">{message}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onReset}
        className="mt-5 inline-flex items-center gap-2 rounded bg-danger px-4 py-2 font-semibold text-white hover:bg-red-800"
      >
        <RotateCcw aria-hidden="true" className="h-5 w-5" />
        重新開始
      </button>
    </section>
  );
}
