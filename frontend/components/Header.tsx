"use client";

import { AlertTriangle, Scale, Wallet } from "lucide-react";
import { shortAddr } from "@/lib/chain";
import { useApp } from "./Providers";
import { Button } from "./ui";

export function Header({ onHome }: { onHome: () => void }) {
  const { account, chainOk, connect, fixNetwork } = useApp();
  return (
    <>
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 shadow-sm backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <button onClick={onHome} className="flex items-center gap-2 text-left">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 text-white shadow-sm">
              <Scale className="h-5 w-5" />
            </span>
            <span>
              <span className="block text-base font-bold leading-tight text-slate-900">OddsX Clearinghouse</span>
              <span className="block text-xs text-slate-600">Subjective markets · GenLayer consensus</span>
            </span>
          </button>
          {account ? (
            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-sm text-slate-700 shadow-sm">
              <span className={`h-2 w-2 rounded-full ${chainOk ? "bg-emerald-500" : "bg-amber-500"}`} />
              <span className="font-mono">{shortAddr(account)}</span>
            </div>
          ) : (
            <Button onClick={connect}>
              <Wallet className="h-4 w-4" /> Connect wallet
            </Button>
          )}
        </div>
      </header>
      {account && !chainOk && (
        <div className="border-b border-amber-200 bg-amber-50">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-2 text-sm text-amber-800">
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" /> Your wallet is not on GenLayer Studio Next (chain 61997).
            </span>
            <Button variant="danger" onClick={fixNetwork}>
              Switch network
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
