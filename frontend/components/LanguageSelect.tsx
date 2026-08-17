"use client";

import { languages, type LanguageCode } from "@/lib/types";

interface LanguageSelectProps {
  sourceLanguage: LanguageCode;
  targetLanguage: LanguageCode;
  disabled: boolean;
  onSourceChange: (value: LanguageCode) => void;
  onTargetChange: (value: LanguageCode) => void;
}

export function LanguageSelect({
  sourceLanguage,
  targetLanguage,
  disabled,
  onSourceChange,
  onTargetChange
}: LanguageSelectProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <label className="grid gap-2 text-sm font-medium text-ink">
        原始語言
        <select
          disabled={disabled}
          value={sourceLanguage}
          onChange={(event) => onSourceChange(event.target.value as LanguageCode)}
          className="h-11 rounded border border-line bg-white px-3 text-base disabled:bg-slate-100"
        >
          {languages.map((language) => (
            <option key={language.code} value={language.code}>
              {language.label}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-2 text-sm font-medium text-ink">
        目標語言
        <select
          disabled={disabled}
          value={targetLanguage}
          onChange={(event) => onTargetChange(event.target.value as LanguageCode)}
          className="h-11 rounded border border-line bg-white px-3 text-base disabled:bg-slate-100"
        >
          {languages.map((language) => (
            <option key={language.code} value={language.code}>
              {language.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
