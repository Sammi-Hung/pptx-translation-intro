import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PowerPoint 簡報翻譯與語音嵌入",
  description: "公司內部使用的 PowerPoint 翻譯與講者備註語音嵌入工具"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}

