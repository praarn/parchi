const STYLES: Record<string, string> = {
  uploaded: "bg-paper-sunk text-ink-soft",
  processing: "bg-amber-wash text-amber-dark",
  ready: "bg-teal-wash text-teal-dark",
  failed: "bg-danger/10 text-danger",
};

const LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-xs font-semibold ${
        STYLES[status] ?? STYLES.uploaded
      }`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {LABELS[status] ?? status}
    </span>
  );
}
