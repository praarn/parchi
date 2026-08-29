"use client";

import { useCallback, useState } from "react";
import { UploadCloud, FileText, ImageIcon } from "lucide-react";

const ACCEPTED = ["application/pdf", "image/png", "image/jpeg", "image/webp"];

export function UploadDropzone({
  onFileSelected,
  onReject,
  busy = false,
}: {
  onFileSelected: (file: File) => void;
  onReject?: (message: string) => void;
  busy?: boolean;
}) {
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [isImage, setIsImage] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      if (!ACCEPTED.includes(file.type)) {
        onReject?.("That file type isn't supported. Upload a PDF or a photo (PNG, JPEG, WebP).");
        return;
      }
      setFileName(file.name);
      setIsImage(file.type.startsWith("image/"));
      onFileSelected(file);
    },
    [onFileSelected, onReject],
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
      className={`flex flex-col items-center justify-center gap-4 rounded-card border-2 border-dashed p-10 text-center transition ${
        dragging ? "border-amber bg-amber-wash" : "border-line bg-paper-raised"
      } ${busy ? "opacity-60" : ""}`}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-wash text-teal">
        {fileName ? (
          isImage ? (
            <ImageIcon className="h-6 w-6" />
          ) : (
            <FileText className="h-6 w-6" />
          )
        ) : (
          <UploadCloud className="h-6 w-6" />
        )}
      </span>
      <div>
        <p className="text-lg font-semibold text-ink">
          {fileName ?? "Drop your document here"}
        </p>
        <p className="mt-1 text-sm text-ink-muted">
          PDF or a photo of the page — up to 50&nbsp;MB
        </p>
      </div>
      <label className={`btn-primary ${busy ? "pointer-events-none" : "cursor-pointer"}`}>
        {busy ? "Uploading…" : "Choose a file"}
        <input
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          disabled={busy}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>
    </div>
  );
}
