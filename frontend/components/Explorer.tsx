"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Coins, Gavel, Layers, Plus, RefreshCw, ShieldCheck, Timer } from "lucide-react";
import { chain, formatGen, phaseOf } from "@/lib/chain";
import type { Market, Phase } from "@/lib/types";
import { CreateMarket } from "./CreateMarket";
import { useApp } from "./Providers";
import { Button, PhaseBadge, VerdictBadge } from "./ui";

const FILTERS: { key: "all" | Phase; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "awaiting", label: "Resolving" },
  { key: "resolved", label: "Challenge window" },
  { key: "final", label: "Resolved" },
];

export function Explorer({ onOpen }: { onOpen: (id: number) => void }) {
  const { now, notify } = useApp();
  const [markets, setMarkets] = useState<Market[] | null>(null);
  const [filter, setFilter] = useState<"all" | Phase>("all");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setMarkets(await chain.allMarkets());
    } catch (err) {
      setMarkets([]);
      notify("error", err instanceof Error ? `Could not load markets: ${err.message}` : "Could not load markets.");
    }
  }, [notify]);

  useEffect(() => {
    void load();
  }, [load]);

  const stats = useMemo(() => {
    const list = markets ?? [];
    let volume = BigInt(0);
    let resolved = 0;
    let challengeable = 0;
    let challenged = 0;
    for (const m of list) {
      volume += BigInt(m.yes_pool) + BigInt(m.no_pool);
      if (m.status === "FINAL") resolved += 1;
      if (m.status === "RESOLVED") challengeable += 1;
      if (m.challenged) challenged += 1;
    }
    return { volume, resolved, challengeable, challenged, total: list.length };
  }, [markets]);

  const visible = (markets ?? []).filter((m) => filter === "all" || phaseOf(m, now) === filter);

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-slate-50 px-6 py-10 ring-1 ring-slate-200 sm:px-12 sm:py-14">
        <div className="bg-grid-slate mask-fade-b pointer-events-none absolute inset-0" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_70%_at_50%_0%,rgba(99,102,241,0.10),transparent)]" />
        <div className="relative mx-auto flex max-w-3xl flex-col items-center text-center">
          <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-600 shadow-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Live on GenLayer Studio Next
          </span>
          <h1 className="bg-gradient-to-r from-slate-900 to-slate-600 bg-clip-text pb-1 text-4xl font-extrabold leading-[1.1] tracking-tight text-transparent sm:text-6xl">
            Markets for questions that need judgment
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-600 sm:text-lg">
            Validators read the sources and publish an auditable reasoning trace. Disagree with the verdict? Stake a
            bond and escalate to a deeper audit.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New market
            </Button>
            <Button variant="outline" onClick={load}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
          </div>
        </div>
      </section>

      {/* Command-center stats strip */}
      <section className="grid grid-cols-2 divide-x divide-slate-100 overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200 lg:grid-cols-4 [&>*:nth-child(n+3)]:border-t [&>*:nth-child(n+3)]:border-slate-100 lg:[&>*:nth-child(n+3)]:border-t-0">
        <StatCell icon={<Coins className="h-4 w-4" />} label="Total volume" value={formatGen(stats.volume)} unit="GEN" loaded={markets !== null} />
        <StatCell icon={<Layers className="h-4 w-4" />} label="Markets" value={String(stats.total)} loaded={markets !== null} />
        <StatCell icon={<ShieldCheck className="h-4 w-4" />} label="Resolved" value={String(stats.resolved)} loaded={markets !== null} />
        <StatCell
          icon={<Gavel className="h-4 w-4" />}
          label="Open to challenge"
          value={String(stats.challengeable)}
          sub={`${stats.challenged} settled by dispute`}
          loaded={markets !== null}
        />
      </section>

      {/* Filters + grid */}
      <section>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold tracking-tight text-slate-900">Market Explorer</h2>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-all duration-200 ${
                  filter === f.key
                    ? "border-indigo-600 bg-indigo-600 text-white shadow-sm"
                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {markets === null ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-52 animate-pulse rounded-2xl border border-slate-200 bg-white shadow-sm" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-600">
            No markets match this filter yet.
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((m) => (
              <MarketCard key={m.id} market={m} onOpen={() => onOpen(m.id)} />
            ))}
          </div>
        )}
      </section>

      {creating && (
        <CreateMarket
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            void load();
          }}
        />
      )}
    </div>
  );
}

function StatCell({
  icon,
  label,
  value,
  unit,
  sub,
  loaded,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  loaded: boolean;
}) {
  return (
    <div className="px-5 py-5 sm:px-7">
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        <span className="text-slate-400">{icon}</span> {label}
      </p>
      <p className="font-mono text-2xl font-semibold tracking-tight text-slate-900">
        {loaded ? value : "–"}
        {unit && loaded && <span className="ml-1.5 text-sm font-medium text-slate-400">{unit}</span>}
      </p>
      <p className="mt-1 h-4 text-xs text-slate-500">{loaded ? sub ?? "" : ""}</p>
    </div>
  );
}

function MarketCard({ market: m, onOpen }: { market: Market; onOpen: () => void }) {
  const { now } = useApp();
  const phase = phaseOf(m, now);
  const yes = BigInt(m.yes_pool);
  const no = BigInt(m.no_pool);
  const total = yes + no;
  const yesPct = total === BigInt(0) ? 50 : Number((yes * BigInt(100)) / total);
  const daysLeft = Math.ceil((m.resolution_date - now) / 86400);

  return (
    <button onClick={onOpen} className="group block w-full text-left">
      <article className="flex h-full flex-col rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200/60 transition-all duration-300 group-hover:-translate-y-0.5 group-hover:shadow-md group-hover:ring-slate-300">
        <div className="mb-3 flex items-center justify-between gap-2">
          <PhaseBadge phase={phase} />
          <VerdictBadge verdict={m.verdict} />
        </div>
        <h2 className="mb-5 line-clamp-3 flex-1 text-[17px] font-semibold leading-snug tracking-tight text-slate-900">
          {m.title}
        </h2>

        {/* Odds: percentages inline above a stacked bar */}
        <div className="mb-1.5 flex items-center justify-between font-mono text-xs font-semibold">
          <span className="inline-flex items-center gap-1.5 text-emerald-600">
            <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] tracking-wider text-emerald-700 ring-1 ring-emerald-200">YES</span>
            {yesPct}%
          </span>
          <span className="inline-flex items-center gap-1.5 text-rose-600">
            {100 - yesPct}%
            <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] tracking-wider text-rose-700 ring-1 ring-rose-200">NO</span>
          </span>
        </div>
        <div className="mb-4 flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-slate-100 p-px ring-1 ring-inset ring-slate-200/70">
          <div className="h-full rounded-l-full rounded-r-sm bg-emerald-500 transition-all duration-500" style={{ width: `${yesPct}%` }} />
          <div className="h-full flex-1 rounded-l-sm rounded-r-full bg-rose-500" />
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Coins className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.75} />
            <span className="font-mono">{formatGen(total)}</span> GEN
          </span>
          <span className="inline-flex items-center gap-1">
            <BookOpen className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.75} />
            {m.resolution_sources.length} source{m.resolution_sources.length === 1 ? "" : "s"}
          </span>
          <span className="inline-flex items-center gap-1">
            <Timer className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.75} />
            {phase === "active" ? (daysLeft > 0 ? `${daysLeft}d left` : "<1d left") : phase === "final" ? "Settled" : "Closed"}
          </span>
        </div>
      </article>
    </button>
  );
}
