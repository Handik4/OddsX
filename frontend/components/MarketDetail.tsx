"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Clock, ExternalLink, Gavel, ShieldAlert, Trophy } from "lucide-react";
import { chain, formatGen, phaseOf, shortAddr, toAtto, write } from "@/lib/chain";
import type { Config, Market, Position } from "@/lib/types";
import { EXPLORER_URL, CONTRACT_ADDRESS } from "@/lib/config";
import { useApp } from "./Providers";
import { TraceViewer } from "./TraceViewer";
import { Button, Card, PhaseBadge, SectionTitle, VerdictBadge, countdown, inputCls } from "./ui";

export function MarketDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const { account, now, notify } = useApp();
  const [market, setMarket] = useState<Market | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [payout, setPayout] = useState("0");
  const [claimable, setClaimable] = useState("0");
  const [config, setConfig] = useState<Config | null>(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const [m, c] = await Promise.all([chain.market(id), chain.config()]);
      setMarket(m);
      setConfig(c);
      if (account) {
        const [pos, pay, cl] = await Promise.all([
          chain.position(id, account),
          chain.preview(id, account),
          chain.claimable(account),
        ]);
        setPosition(pos);
        setPayout(pay);
        setClaimable(cl);
      }
    } catch (err) {
      notify("error", err instanceof Error ? `Could not load market: ${err.message}` : "Could not load market.");
    }
  }, [id, account, notify]);

  useEffect(() => {
    void load();
  }, [load]);

  // Run a contract write with consistent progress, error and refresh handling.
  async function run(label: string, fn: string, args: unknown[], value = BigInt(0), done?: string) {
    if (!account) {
      notify("error", "Connect your wallet first.");
      return;
    }
    setBusy(label);
    try {
      await write(account, fn, args, value, () => notify("info", "Transaction submitted. Validators are reaching consensus…"));
      notify("success", done ?? "Transaction confirmed.");
      await load();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Transaction failed.");
    } finally {
      setBusy("");
    }
  }

  if (!market || !config) return <p className="text-slate-600">Loading market…</p>;

  const phase = phaseOf(market, now);
  const total = BigInt(market.yes_pool) + BigInt(market.no_pool);
  const yesPct = total === BigInt(0) ? 50 : Number((BigInt(market.yes_pool) * BigInt(100)) / total);
  const windowLeft = market.challenge_deadline - now;

  return (
    <div className="space-y-6">
      <button onClick={onBack} className="inline-flex items-center gap-1 text-sm font-medium text-indigo-700 hover:underline">
        <ArrowLeft className="h-4 w-4" /> All markets
      </button>

      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <PhaseBadge phase={phase} />
          <VerdictBadge verdict={market.verdict} />
          {market.challenged && (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
              {market.overturned ? "Overturned on challenge" : "Upheld on challenge"}
            </span>
          )}
        </div>
        <h1 className="text-2xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-3xl">{market.title}</h1>
        {market.description && <p className="mt-3 text-base leading-relaxed text-slate-600">{market.description}</p>}
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
          <Stat label="Total pool" value={`${formatGen(total)} GEN`} />
          <Stat label="Resolves" value={new Date(market.resolution_date * 1000).toLocaleString()} />
          <Stat label="Creator" value={shortAddr(market.creator)} />
        </div>
        <div className="mt-5">
          <div className="mb-1 flex justify-between text-sm font-medium">
            <span className="font-bold text-emerald-600">YES · {formatGen(market.yes_pool)} GEN ({yesPct}%)</span>
            <span className="font-bold text-rose-600">NO · {formatGen(market.no_pool)} GEN ({100 - yesPct}%)</span>
          </div>
          <div className="flex h-3.5 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-emerald-500 transition-all duration-500" style={{ width: `${yesPct}%` }} />
            <div className="h-full flex-1 rounded-full bg-rose-500" />
          </div>
        </div>
        <div className="mt-4">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Resolution sources</p>
          <ul className="space-y-1">
            {market.resolution_sources.map((s) => (
              <li key={s}>
                <a href={s} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 break-all text-sm text-indigo-700 hover:underline">
                  {s} <ExternalLink className="h-3 w-3 shrink-0" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      </Card>

      {position && (BigInt(position.yes) > BigInt(0) || BigInt(position.no) > BigInt(0)) && (
        <Card>
          <SectionTitle>Your position</SectionTitle>
          <p className="text-sm text-slate-700">
            YES {formatGen(position.yes)} GEN · NO {formatGen(position.no)} GEN (net of the {config.fee_bps / 100}% fee)
          </p>
        </Card>
      )}

      {phase === "active" && (
        <BetPanel
          minBet={config.min_bet}
          feePct={config.fee_bps / 100}
          busy={busy}
          onBet={(side, amount) =>
            run("bet", "place_bet", [id, side], toAtto(amount), `Bet placed on ${side}.`)
          }
        />
      )}

      {phase === "awaiting" && (
        <Card>
          <SectionTitle hint="Betting is closed. Anyone can trigger Layer 1: validators fetch the sources and reach consensus on a verdict and reasoning trace.">
            Resolve this market
          </SectionTitle>
          <Button busy={busy === "resolve"} onClick={() => run("resolve", "resolve_market", [id], BigInt(0), "Market resolved at Layer 1.")}>
            <Gavel className="h-4 w-4" /> Run Layer 1 resolution
          </Button>
        </Card>
      )}

      {market.reasoning_trace && (
        <section className="space-y-4">
          <h2 className="text-xl font-extrabold tracking-tight text-slate-900">Resolution &amp; reasoning trace</h2>
          {market.challenged && (
            <p
              className={`rounded-xl border p-4 text-sm font-medium ${
                market.overturned ? "border-amber-200 bg-amber-50 text-amber-800" : "border-indigo-200 bg-indigo-50 text-indigo-800"
              }`}
            >
              {market.overturned
                ? `The Layer 3 audit overturned the Layer 1 verdict (${market.original_verdict} → ${market.verdict}). The challenger was refunded and rewarded.`
                : `The Layer 3 audit upheld the Layer 1 verdict (${market.verdict}). The challenger's bond was slashed into the accurate-bettor pool.`}
            </p>
          )}
          <TraceViewer
            title={market.challenged ? "Final verdict · deep trace" : "Validator consensus"}
            verdict={market.verdict}
            trace={market.reasoning_trace}
          />
          {market.challenged && (
            <>
              <TraceViewer title="Original Layer 1 trace" verdict={market.original_verdict} trace={market.original_trace} tone="superseded" />
              {market.challenge_reason && (
                <Card>
                  <SectionTitle>Challenger&apos;s argument</SectionTitle>
                  <p className="whitespace-pre-wrap text-sm text-slate-700">{market.challenge_reason}</p>
                  <p className="mt-2 text-xs text-slate-500">Challenger {shortAddr(market.challenger)}</p>
                </Card>
              )}
            </>
          )}
        </section>
      )}

      {phase === "resolved" && (
        <ChallengeTerminal
          bond={config.challenge_bond}
          windowLeft={windowLeft}
          busy={busy}
          onChallenge={(reason) =>
            run("challenge", "challenge_resolution", [id, reason], BigInt(config.challenge_bond), "Challenge settled at Layer 3.")
          }
          onFinalize={() => run("finalize", "finalize_market", [id], BigInt(0), "Market finalized.")}
        />
      )}

      {phase === "final" && (
        <Card>
          <SectionTitle>Settlement</SectionTitle>
          {market.refund_mode ? (
            <p className="mb-3 text-sm text-slate-600">
              This market ended with no payable winners (inconclusive, or nobody backed the winning side). Net stakes are refunded.
            </p>
          ) : null}
          {!account ? (
            <p className="text-sm text-slate-600">Connect your wallet to see your payout.</p>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm text-slate-700">
                <Trophy className="h-4 w-4 text-indigo-600" />
                Claimable from this market: <b className="text-slate-900">{formatGen(payout)} GEN</b>
                {BigInt(claimable) > BigInt(0) && <span>· Wallet balance owed: {formatGen(claimable)} GEN</span>}
              </div>
              <Button
                busy={busy === "claim"}
                disabled={BigInt(payout) === BigInt(0) && BigInt(claimable) === BigInt(0)}
                onClick={() =>
                  BigInt(payout) > BigInt(0)
                    ? run("claim", "claim_winnings", [id], BigInt(0), "Winnings sent.")
                    : run("claim", "withdraw", [], BigInt(0), "Balance withdrawn.")
                }
              >
                Claim
              </Button>
            </div>
          )}
        </Card>
      )}

      <p className="text-xs text-slate-500">
        Contract{" "}
        <a className="text-indigo-700 hover:underline" target="_blank" rel="noreferrer" href={`${EXPLORER_URL}/address/${CONTRACT_ADDRESS}`}>
          {shortAddr(CONTRACT_ADDRESS)}
        </a>{" "}
        on GenLayer Studio Next
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-base font-bold text-slate-900">{value}</p>
    </div>
  );
}

function BetPanel({
  minBet,
  feePct,
  busy,
  onBet,
}: {
  minBet: string;
  feePct: number;
  busy: string;
  onBet: (side: "YES" | "NO", amount: string) => void;
}) {
  const [amount, setAmount] = useState("1");
  const valid = Number(amount) >= Number(formatGen(minBet, 6));
  return (
    <Card>
      <SectionTitle hint={`A ${feePct}% fee on each bet funds the challenge reward pool. Winners split the whole net pool pro rata.`}>
        Place a bet
      </SectionTitle>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex-1 text-sm font-medium text-slate-900">
          Amount (GEN)
          <input className={`${inputCls} mt-1 font-normal`} type="number" min="0" step="any" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <Button variant="yes" disabled={!valid} busy={busy === "bet"} onClick={() => onBet("YES", amount)}>
          Bet YES
        </Button>
        <Button variant="no" disabled={!valid} busy={busy === "bet"} onClick={() => onBet("NO", amount)}>
          Bet NO
        </Button>
      </div>
      {!valid && <p className="mt-2 text-xs text-rose-700">Minimum bet is {formatGen(minBet, 6)} GEN.</p>}
    </Card>
  );
}

function ChallengeTerminal({
  bond,
  windowLeft,
  busy,
  onChallenge,
  onFinalize,
}: {
  bond: string;
  windowLeft: number;
  busy: string;
  onChallenge: (reason: string) => void;
  onFinalize: () => void;
}) {
  const [reason, setReason] = useState("");
  const open = windowLeft > 0;
  return (
    <Card className="border-indigo-200 bg-gradient-to-b from-indigo-50/60 to-white">
      <SectionTitle hint="Disagree with the Layer 1 verdict? Stake the bond to trigger a deeper Layer 3 audit. If it overturns the verdict you get the bond back plus the market fee pool. If the verdict stands, your bond is slashed and paid to the accurate bettors.">
        Challenge terminal
      </SectionTitle>
      <div className="mb-3 flex items-center gap-2 text-sm text-slate-700">
        <Clock className="h-4 w-4 text-indigo-600" />
        {open ? <>Window closes in <b className="text-slate-900">{countdown(windowLeft)}</b></> : "Challenge window closed"}
      </div>
      {open ? (
        <>
          <label className="block text-sm font-medium text-slate-900">
            Why is the verdict wrong?
            <textarea className={`${inputCls} mt-1 font-normal`} rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Point to the source passage or logical gap the validators missed." />
          </label>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-1.5 text-sm text-amber-700">
              <ShieldAlert className="h-4 w-4" /> Bond at risk: {formatGen(bond)} GEN
            </p>
            <Button variant="danger" busy={busy === "challenge"} onClick={() => onChallenge(reason)}>
              Stake bond &amp; challenge
            </Button>
          </div>
        </>
      ) : (
        <Button busy={busy === "finalize"} onClick={onFinalize}>
          Finalize market
        </Button>
      )}
    </Card>
  );
}
