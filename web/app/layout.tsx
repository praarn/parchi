import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Saral — Government Documents, Explained Simply",
  description: "Upload any government document and get a plain-language summary, eligibility checklist, and answers to your questions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-body antialiased">{children}</body>
    </html>
  );
}