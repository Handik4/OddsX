"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { write } from "@/lib/chain";
import { useApp } from "./Providers";
import { Button, inputCls } from "./ui";

export function CreateMarket({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { account, connect, notify } = useApp();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [sources, setSources] = useState("");
  const [days, setDays] = useState("3");
  const [busy, setBusy] = useState(false);

  async function submit() {
    const urls = sources
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const when = Math.floor(Date.now() / 1000) + Math.round(Number(days) * 86400);
    if (!title.trim() || urls.length === 0 || !(Number(days) > 0)) {
      notify("error", "Add a title, at least one source URL, and a positive number of days.");
      return;
    }
    setBusy(true);
    try {
      await write(account, "create_market", [title, description, urls, when], BigInt(0), () =>
        notify("info", "Transaction submitted. Waiting for consensus…")
      );
      notify("success", "Market created.");
      onCreated();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Transaction failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="max-h-full w-full max-w-lg overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Create a subjective market</h2>
          <button onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-4">
          <label className="block text-sm font-medium text-slate-900">
            Question
            <input className={`${inputCls} mt-1 font-normal`} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Did the ruling violate term X?" />
          </label>
          <label className="block text-sm font-medium text-slate-900">
            Resolution criteria
            <textarea className={`${inputCls} mt-1 font-normal`} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Resolves YES if… NO if… INCONCLUSIVE if…" />
          </label>
          <label className="block text-sm font-medium text-slate-900">
            Resolution sources (one URL per line, up to 5)
            <textarea className={`${inputCls} mt-1 font-mono text-xs font-normal`} rows={3} value={sources} onChange={(e) => setSources(e.target.value)} placeholder="https://…" />
          </label>
          <label className="block text-sm font-medium text-slate-900">
            Resolves in (days)
            <input className={`${inputCls} mt-1 font-normal`} type="number" min="0.01" step="any" value={days} onChange={(e) => setDays(e.target.value)} />
          </label>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          {account ? (
            <Button onClick={submit} busy={busy}>
              Create market
            </Button>
          ) : (
            <Button onClick={connect}>Connect wallet</Button>
          )}
        </div>
      </div>
    </div>
  );
}
