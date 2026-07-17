"use client";

import { useCallback, useState } from "react";
import { UploadCloud, FileText } from "lucide-react";

export function UploadDropzone({ onFileSelected }: { onFileSelected: (file: File) => void }) {
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      if (file.type !== "application/pdf") {
        alert("Please upload a PDF file.");
        return;
      }
      setFileName(file.name);
      onFileSelected(file);
    },
    [onFileSelected]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={`flex flex-col items-center justify-center gap-4 rounded-3xl border-4 border-dashed p-12 text-center transition-colors ${
        dragging ? "border-amber bg-amber/10" : "border-teal/30 bg-white"
      }`}
    >
      {fileName ? <FileText className="h-12 w-12 text-teal" /> : <UploadCloud className="h-12 w-12 text-teal" />}
      <div>
        <p className="text-xl font-semibold text-ink">
          {fileName ? fileName : "Drop your document here"}
        </p>
        <p className="mt-1 text-base text-ink/60">or choose a file from your device — PDF, up to 50MB</p>
      </div>
      <label className="cursor-pointer rounded-full bg-teal px-6 py-3 text-base font-semibold text-white hover:bg-teal-dark">
        Choose file
        <input
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>
    </div>
  );
}