"use client";

import { useState } from "react";
import { Explorer } from "@/components/Explorer";
import { Header } from "@/components/Header";
import { MarketDetail } from "@/components/MarketDetail";
import { Providers } from "@/components/Providers";
import { Toasts } from "@/components/ui";
import { CONTRACT_ADDRESS } from "@/lib/config";

export default function Page() {
  const [selected, setSelected] = useState<number | null>(null);
  return (
    <Providers>
      <Header onHome={() => setSelected(null)} />
      <main className="mx-auto w-full max-w-6xl flex-grow px-4 py-8">
        {!CONTRACT_ADDRESS ? (
          <p className="rounded-xl border border-amber-200 bg-white p-5 text-slate-700 shadow-sm">
            Set NEXT_PUBLIC_ODDSX_CONTRACT_ADDRESS in frontend/.env.local (run scripts/deploy.py to create it).
          </p>
        ) : selected === null ? (
          <Explorer onOpen={setSelected} />
        ) : (
          <MarketDetail id={selected} onBack={() => setSelected(null)} />
        )}
      </main>
      <Toasts />
    </Providers>
  );
}
