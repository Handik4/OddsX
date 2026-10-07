"use client";

import { Loader2, X } from "lucide-react";
import type { Phase, Verdict } from "@/lib/types";
import { useApp } from "./Providers";

export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 ${className}`}>{children}</div>
  );
}

export function SectionTitle({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="mb-3">
      <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900">{children}</h3>
      {hint && <p className="mt-1 text-sm text-slate-600">{hint}</p>}
    </div>
  );
}

const PHASE_STYLE: Record<Phase, { label: string; text: string; dot: string }> = {
  active: { label: "Active", text: "text-emerald-700", dot: "bg-emerald-500" },
  awaiting: { label: "Resolving", text: "text-amber-700", dot: "bg-amber-500" },
  resolved: { label: "Challenge window", text: "text-indigo-700", dot: "bg-indigo-500" },
  final: { label: "Resolved", text: "text-slate-600", dot: "bg-slate-400" },
};

export function PhaseBadge({ phase }: { phase: Phase }) {
  const s = PHASE_STYLE[phase];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider shadow-sm ${s.text}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {phase === "active" && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${s.dot}`} />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${s.dot}`} />
      </span>
      {s.label}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  if (!verdict) return null;
  const cls =
    verdict === "YES"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : verdict === "NO"
        ? "border-rose-200 bg-rose-50 text-rose-700"
        : "border-slate-200 bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 font-mono text-[11px] font-bold tracking-wider shadow-sm ${cls}`}>
      {verdict}
    </span>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  busy,
  variant = "primary",
  className = "",
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "yes" | "no" | "outline" | "danger";
  className?: string;
  type?: "button" | "submit";
}) {
  const styles: Record<string, string> = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700",
    yes: "bg-emerald-600 text-white hover:bg-emerald-700",
    no: "bg-rose-600 text-white hover:bg-rose-700",
    danger: "bg-amber-600 text-white hover:bg-amber-700",
    outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || busy}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    >
      {busy && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100";

export function Toasts() {
  const { toasts, dismiss } = useApp();
  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-2 rounded-lg border bg-white p-3 text-sm shadow-sm ${
            t.kind === "error"
              ? "border-rose-200 text-rose-700"
              : t.kind === "success"
                ? "border-emerald-200 text-emerald-700"
                : "border-slate-200 text-slate-700"
          }`}
        >
          <span className="flex-1 break-words">{t.text}</span>
          <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="text-slate-400 hover:text-slate-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}

export function countdown(seconds: number): string {
  if (seconds <= 0) return "0s";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s}s`;
}
