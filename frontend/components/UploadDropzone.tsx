"use client";

import { FileUp, X } from "lucide-react";
import { useRef, useState } from "react";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

interface UploadDropzoneProps {
  file: File | null;
  disabled: boolean;
  onFileChange: (file: File | null, error?: string) => void;
}

export function UploadDropzone({ file, disabled, onFileChange }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  function acceptFile(nextFile: File | undefined) {
    if (!nextFile) return;
    if (!nextFile.name.toLowerCase().endsWith(".pptx")) {
      onFileChange(null, "只支援 .pptx 檔案。");
      return;
    }
    if (nextFile.size > MAX_UPLOAD_BYTES) {
      onFileChange(null, "檔案大小不能超過 50 MB。");
      return;
    }
    onFileChange(nextFile);
  }

  return (
    <div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          if (!disabled) acceptFile(event.dataTransfer.files[0]);
        }}
        className={`flex min-h-[360px] w-full flex-col items-center justify-center gap-5 rounded border-2 border-dashed px-8 text-center transition ${
          dragOver ? "border-brand bg-blue-50" : "border-line bg-white"
        } disabled:cursor-not-allowed disabled:bg-slate-100`}
      >
        <span className="grid h-20 w-20 place-items-center rounded-full bg-blue-50 text-brand">
          <FileUp aria-hidden="true" className="h-10 w-10" />
        </span>
        <span className="text-2xl font-semibold">點擊或拖曳 PowerPoint 檔案</span>
        <span className="max-w-md text-sm leading-6 text-slate-600">
          僅支援 .pptx，最大 50 MB。處理期間會鎖定上傳與語言選單，避免重複送出。
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pptx"
        className="hidden"
        disabled={disabled}
        onChange={(event) => acceptFile(event.target.files?.[0])}
      />
      {file ? (
        <div className="mt-4 flex items-center justify-between rounded border border-line bg-white px-4 py-3">
          <div>
            <p className="font-medium">{file.name}</p>
            <p className="text-sm text-slate-600">{formatBytes(file.size)}</p>
          </div>
          <button
            type="button"
            disabled={disabled}
            aria-label="移除檔案"
            onClick={() => onFileChange(null)}
            className="rounded p-2 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
          >
            <X aria-hidden="true" className="h-5 w-5" />
          </button>
        </div>
      ) : null}
    </div>
  );
}
