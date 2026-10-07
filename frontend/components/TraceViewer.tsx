"use client";

import { ExternalLink, FileText, Gavel, ShieldCheck, Terminal } from "lucide-react";
import type { Verdict } from "@/lib/types";
import { VerdictBadge } from "./ui";

interface ParsedTrace {
  layer: string;
  sources: { index: string; url: string; note: string }[];
  reasoning: string;
}

// Traces are written by the contract as "<LAYER> | Sources: [1] url (note); [2] …\n<reasoning>".
export function parseTrace(trace: string): ParsedTrace {
  const [head, ...rest] = trace.split("\n");
  const [layerPart, sourcePart = ""] = head.split(" | Sources: ");
  const sources = sourcePart
    .split("; ")
    .map((chunk) => {
      const m = chunk.match(/^\[(\d+)\]\s+(\S+)\s+\((.*)\)$/);
      return m ? { index: m[1], url: m[2], note: m[3] } : null;
    })
    .filter((s): s is { index: string; url: string; note: string } => s !== null);
  return { layer: layerPart.trim(), sources, reasoning: rest.join("\n").trim() };
}

// Highlights "[1]"-style source citations inside a line of reasoning.
function renderLine(line: string) {
  return line.split(/(\[\d+\])/g).map((part, i) =>
    /^\[\d+\]$/.test(part) ? (
      <span key={i} className="mx-0.5 rounded bg-indigo-50 px-1 font-semibold text-indigo-700">
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export function TraceViewer({
  title,
  verdict,
  trace,
  tone = "default",
}: {
  title: string;
  verdict: Verdict;
  trace: string;
  tone?: "default" | "superseded";
}) {
  const parsed = parseTrace(trace);
  const lines = parsed.reasoning.split(/\n+/).filter(Boolean);
  const superseded = tone === "superseded";
  return (
    <div
      className={`overflow-hidden rounded-2xl border bg-white shadow-sm ${
        superseded ? "border-dashed border-slate-300" : "border-slate-200"
      }`}
    >
      {/* Terminal title bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-100 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="flex gap-1.5" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
          </span>
          <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-slate-700">
            <Terminal className="h-3.5 w-3.5" /> {superseded ? "superseded-trace.log" : "reasoning-trace.log"}
          </span>
        </div>
        <span className="inline-flex items-center gap-1.5 font-mono text-xs text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" /> validator consensus
        </span>
      </div>

      {/* Audit header */}
      <div className="border-b border-slate-200 bg-slate-50 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[11px] font-semibold uppercase tracking-widest text-slate-500">Audit record</p>
            <h3 className="mt-1 text-base font-bold text-slate-900">{title}</h3>
            <p className="mt-0.5 font-mono text-xs text-slate-600">{parsed.layer}</p>
          </div>
          <div className="text-right">
            <p className="mb-1 font-mono text-[11px] font-semibold uppercase tracking-widest text-slate-500">Verdict</p>
            <VerdictBadge verdict={verdict} />
          </div>
        </div>
      </div>

      {/* Sources */}
      <div className="border-b border-slate-200 px-5 py-4">
        <p className="mb-2.5 flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-widest text-slate-500">
          <FileText className="h-3.5 w-3.5" /> Sources consulted ({parsed.sources.length})
        </p>
        <ul className="space-y-2">
          {parsed.sources.map((src) => (
            <li key={src.index} className="flex items-start gap-2.5 font-mono text-xs">
              <span className="flex h-5 w-6 shrink-0 items-center justify-center rounded bg-indigo-50 font-bold text-indigo-700">
                [{src.index}]
              </span>
              <a
                href={src.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-w-0 items-center gap-1 break-all text-slate-700 hover:text-indigo-700 hover:underline"
              >
                {src.url} <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
              <span
                className={`ml-auto shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                  src.note === "fetched"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-amber-200 bg-amber-50 text-amber-700"
                }`}
              >
                {src.note}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Reasoning body */}
      <div className="px-5 py-4">
        <p className="mb-3 flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-widest text-slate-500">
          <Gavel className="h-3.5 w-3.5" /> Reasoning trace
        </p>
        <div className="rounded-xl border border-slate-200 bg-slate-50 py-3 font-mono text-sm leading-7 text-slate-800">
          {lines.map((line, i) => (
            <div key={i} className="flex gap-4 px-4 hover:bg-white">
              <span className="w-6 shrink-0 select-none text-right text-xs leading-7 text-slate-400">{i + 1}</span>
              <p className="min-w-0 flex-1 whitespace-pre-wrap break-words">{renderLine(line)}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
