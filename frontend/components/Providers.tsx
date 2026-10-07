"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { CHAIN_ID } from "@/lib/config";
import { connectWallet, currentChainId, getEthereum, switchToStudio } from "@/lib/chain";

interface Toast {
  id: number;
  kind: "info" | "success" | "error";
  text: string;
}

interface AppContextValue {
  account: string;
  chainOk: boolean;
  connect: () => Promise<void>;
  fixNetwork: () => Promise<void>;
  toasts: Toast[];
  notify: (kind: Toast["kind"], text: string) => void;
  dismiss: (id: number) => void;
  now: number;
}

const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside Providers");
  return ctx;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = useState("");
  const [chainId, setChainId] = useState<number | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    const t = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);
    return () => clearInterval(t);
  }, []);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const notify = useCallback(
    (kind: Toast["kind"], text: string) => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t, { id, kind, text }]);
      if (kind !== "error") setTimeout(() => dismiss(id), 6000);
    },
    [dismiss]
  );

  const refreshChain = useCallback(async () => setChainId(await currentChainId()), []);

  const connect = useCallback(async () => {
    try {
      setAccount(await connectWallet());
      await refreshChain();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Could not connect the wallet.");
    }
  }, [notify, refreshChain]);

  const fixNetwork = useCallback(async () => {
    try {
      await switchToStudio();
      await refreshChain();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Could not switch network.");
    }
  }, [notify, refreshChain]);

  // Restore an already-authorized session and follow wallet events. When the
  // wallet is connected on the wrong chain, switch to Studio Next automatically.
  useEffect(() => {
    const eth = getEthereum() as
      | (ReturnType<typeof getEthereum> & {
          on?: (e: string, h: (...a: any[]) => void) => void;
          removeListener?: (e: string, h: (...a: any[]) => void) => void;
        })
      | null;
    if (!eth) return;
    (async () => {
      const accounts = (await eth.request({ method: "eth_accounts" })) as string[];
      if (accounts[0]) {
        setAccount(accounts[0]);
        const id = await currentChainId();
        setChainId(id);
        if (id !== CHAIN_ID) {
          try {
            await switchToStudio();
            await refreshChain();
          } catch {
            /* the banner offers a manual switch */
          }
        }
      }
    })();
    const onAccounts = (a: string[]) => setAccount(a[0] ?? "");
    const onChain = () => void refreshChain();
    eth.on?.("accountsChanged", onAccounts);
    eth.on?.("chainChanged", onChain);
    return () => {
      eth.removeListener?.("accountsChanged", onAccounts);
      eth.removeListener?.("chainChanged", onChain);
    };
  }, [refreshChain]);

  const value = useMemo(
    () => ({
      account,
      chainOk: chainId === CHAIN_ID,
      connect,
      fixNetwork,
      toasts,
      notify,
      dismiss,
      now,
    }),
    [account, chainId, connect, fixNetwork, toasts, notify, dismiss, now]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
