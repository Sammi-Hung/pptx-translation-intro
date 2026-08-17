import { ExternalLink, FileText, Mic2 } from "lucide-react";
import type { ReactNode } from "react";

const usageNotes = [
  "只支援 .pptx，最大 50 MB。",
  "支援繁體中文、英文和泰文。",
  "翻譯投影片文字方塊、指定 Placeholder 和講者備註。",
  "不處理圖片、表格、SmartArt、圖表、頁碼、日期和頁尾。",
  "沒有講者備註的頁面不產生語音。",
  "檔案保留 30 分鐘，下載位置由瀏覽器決定。"
];

const voiceNotes = [
  "語音使用 Windows 本機 SAPI，不需額外雲端費用。",
  "目標語言必須先安裝 Windows 文字轉語音語音包。",
  "安裝路徑：Windows 設定 > 時間與語言 > 語言與地區 > 語言選項。",
  "在語言功能中下載 Text-to-speech / 文字轉語音。",
  "安裝後重新整理本頁；若仍偵測不到，請重啟後端服務。"
];

export function UsageNotes() {
  return (
    <section className="mt-8 grid gap-5 lg:grid-cols-2">
      <InfoBlock
        tone="blue"
        icon={<FileText aria-hidden="true" className="h-5 w-5" />}
        title="使用說明"
        items={usageNotes}
      />
      <InfoBlock
        tone="amber"
        icon={<Mic2 aria-hidden="true" className="h-5 w-5" />}
        title="語音包備註"
        items={voiceNotes}
        link="https://support.microsoft.com/en-us/windows/manage-the-language-and-keyboard-input-layout-settings-in-windows-12a10cb4-8626-9b77-0ccb-5013e0c7c7a2"
      />
    </section>
  );
}

function InfoBlock({
  tone,
  icon,
  title,
  items,
  link
}: {
  tone: "blue" | "amber";
  icon: ReactNode;
  title: string;
  items: string[];
  link?: string;
}) {
  const styles =
    tone === "blue"
      ? "border-blue-100 bg-blue-50/70 text-blue-950"
      : "border-amber-200 bg-amber-50/80 text-amber-950";
  const iconStyles = tone === "blue" ? "bg-white text-brand" : "bg-white text-amber-700";

  return (
    <div className={`rounded border p-5 ${styles}`}>
      <div className="flex items-center gap-3">
        <span className={`grid h-10 w-10 place-items-center rounded ${iconStyles}`}>{icon}</span>
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>
      <ul className="mt-4 grid gap-2 text-sm leading-6">
        {items.map((item) => (
          <li key={item} className="rounded bg-white/70 px-3 py-2">
            {item}
          </li>
        ))}
      </ul>
      {link ? (
        <a
          href={link}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-flex items-center gap-2 text-sm font-semibold underline-offset-4 hover:underline"
        >
          Microsoft 官方說明
          <ExternalLink aria-hidden="true" className="h-4 w-4" />
        </a>
      ) : null}
    </div>
  );
}
