import Link from "next/link";

/** The Parchi wordmark. Latin only. */
export function Brand({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const cls =
    size === "lg"
      ? "text-4xl sm:text-5xl"
      : size === "sm"
        ? "text-xl"
        : "text-2xl";
  return (
    <Link href="/" className="group inline-flex items-baseline gap-2">
      <span
        className={`font-display font-bold tracking-tight text-teal-dark ${cls}`}
      >
        Parchi
      </span>
      <span className="h-2 w-2 rounded-full bg-amber transition group-hover:scale-125" />
    </Link>
  );
}
