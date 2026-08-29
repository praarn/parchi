import type { Metadata, Viewport } from "next";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const body = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Parchi — government paperwork, in plain language",
  description:
    "Upload a government notice, form or letter (PDF or a photo) and get a plain-language summary, an eligibility checklist, key dates and answers to your questions — in your language.",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#0F5257",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="min-h-screen font-body antialiased">{children}</body>
    </html>
  );
}
