"use client";

import type { TranslationOption, TranslationProfile } from "@/lib/types";

interface TranslationModelSelectProps {
  value: TranslationProfile;
  disabled: boolean;
  options: TranslationOption[];
  loading: boolean;
  onChange: (value: TranslationProfile) => void;
}

export function TranslationModelSelect({
  value,
  disabled,
  options,
  loading,
  onChange
}: TranslationModelSelectProps) {
  return (
    <label className="grid gap-2 text-sm font-medium text-ink">
      翻譯模型
      <select
        disabled={disabled || loading || options.length === 0}
        value={value}
        onChange={(event) => onChange(event.target.value as TranslationProfile)}
        className="h-11 rounded border border-line bg-white px-3 text-base disabled:bg-slate-100"
      >
        {loading ? (
          <option value={value}>正在取得模型設定...</option>
        ) : (
          options.map((option) => (
            <option key={option.id} value={option.id} disabled={!option.available}>
              {option.label} - {option.provider} {option.model ?? "未設定"}
            </option>
          ))
        )}
      </select>
    </label>
  );
}
