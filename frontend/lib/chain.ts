"use client";

import { ATTO, CHAIN_ID, CHAIN_ID_HEX, CONTRACT_ADDRESS, EXPLORER_URL, RPC_URL } from "./config";
import type { Config, Market, Phase, Position } from "./types";

interface Eip1193 {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
}

type SdkClient = {
  readContract: (cfg: Record<string, unknown>) => Promise<unknown>;
  writeContract: (cfg: Record<string, unknown>) => Promise<unknown>;
  waitForTransactionReceipt: (cfg: Record<string, unknown>) => Promise<unknown>;
  estimateTransactionFees: (cfg?: Record<string, unknown>) => Promise<unknown>;
};

export function getEthereum(): Eip1193 | null {
  if (typeof window === "undefined") return null;
  return (window as unknown as { ethereum?: Eip1193 }).ethereum ?? null;
}

async function sdkChain() {
  const sdk = (await import("genlayer-js")) as unknown as {
    createClient: (cfg: unknown) => SdkClient;
    chains: Record<string, { rpcUrls: { default: { http: string[] } } }>;
  };
  const shipped = sdk.chains.studioDevnet;
  const chain = { ...shipped, rpcUrls: { default: { http: [RPC_URL] } } };
  return { sdk, chain };
}

let readerPromise: Promise<SdkClient> | null = null;
function reader(): Promise<SdkClient> {
  if (!readerPromise) {
    readerPromise = sdkChain().then(({ sdk, chain }) => sdk.createClient({ chain }));
  }
  return readerPromise;
}

// genlayer-js decodes contract dicts as Map and integers as bigint.
function plain(value: unknown): unknown {
  if (value instanceof Map) {
    const out: Record<string, unknown> = {};
    value.forEach((v, k) => {
      out[String(k)] = plain(v);
    });
    return out;
  }
  if (Array.isArray(value)) return value.map(plain);
  if (typeof value === "bigint") return Number(value);
  return value;
}

async function read<T>(functionName: string, args: unknown[] = []): Promise<T> {
  const client = await reader();
  const raw = await client.readContract({
    address: CONTRACT_ADDRESS,
    functionName,
    args,
  });
  return plain(raw) as T;
}

export const chain = {
  count: () => read<number>("get_market_count"),
  config: () => read<Config>("get_config"),
  market: (id: number) => read<Market>("get_market", [id]),
  position: (id: number, address: string) => read<Position>("get_position", [id, address]),
  preview: (id: number, address: string) => read<string>("preview_payout", [id, address]),
  claimable: (address: string) => read<string>("claimable_of", [address]),
  async allMarkets(): Promise<Market[]> {
    const n = Number(await chain.count());
    const ids = Array.from({ length: n }, (_, i) => n - i);
    return Promise.all(ids.map((id) => chain.market(id)));
  },
};

export async function connectWallet(): Promise<string> {
  const eth = getEthereum();
  if (!eth) throw new Error("No injected wallet found. Install MetaMask to continue.");
  const accounts = (await eth.request({ method: "eth_requestAccounts" })) as string[];
  if (!accounts[0]) throw new Error("The wallet returned no account.");
  await switchToStudio();
  return accounts[0];
}

export async function currentChainId(): Promise<number | null> {
  const eth = getEthereum();
  if (!eth) return null;
  const hex = (await eth.request({ method: "eth_chainId" })) as string;
  return parseInt(hex, 16);
}

export async function switchToStudio(): Promise<void> {
  const eth = getEthereum();
  if (!eth) return;
  try {
    await eth.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_ID_HEX }] });
  } catch (err) {
    if ((err as { code?: number }).code !== 4902) throw err;
    await eth.request({
      method: "wallet_addEthereumChain",
      params: [
        {
          chainId: CHAIN_ID_HEX,
          chainName: "GenLayer Studio Next",
          rpcUrls: [RPC_URL],
          nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
          blockExplorerUrls: [EXPLORER_URL],
        },
      ],
    });
  }
}

export interface WriteResult {
  hash: string;
}

export async function write(
  account: string,
  functionName: string,
  args: unknown[],
  value: bigint = BigInt(0),
  onSubmitted?: (hash: string) => void
): Promise<WriteResult> {
  const eth = getEthereum();
  if (!eth) throw new Error("No injected wallet found.");
  if ((await currentChainId()) !== CHAIN_ID) await switchToStudio();
  const { sdk, chain } = await sdkChain();
  const client = sdk.createClient({ chain, account, provider: eth });
  const fees = await client.estimateTransactionFees();
  const hash = (await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName,
    args,
    value,
    fees,
  })) as string;
  onSubmitted?.(hash);
  const receipt = (await client.waitForTransactionReceipt({
    hash,
    waitUntil: "decided",
    interval: 3000,
    retries: 200,
  })) as Record<string, unknown>;
  const r = receipt as Record<string, unknown>;
  const outcome = String(r.txExecutionResultName ?? r.resultName ?? r.result_name ?? "");
  if (/ERROR|DISAGREE|TIMEOUT|UNDETERMINED/i.test(outcome)) {
    throw new Error(`The contract rejected this transaction (${outcome}).`);
  }
  return { hash };
}

export function phaseOf(m: Market, nowSeconds: number): Phase {
  if (m.status === "FINAL") return "final";
  if (m.status === "RESOLVED") return "resolved";
  return nowSeconds >= m.resolution_date ? "awaiting" : "active";
}

export function toAtto(gen: string): bigint {
  const [whole, frac = ""] = gen.trim().split(".");
  const padded = (frac + "000000000000000000").slice(0, 18);
  return BigInt(whole || "0") * ATTO + BigInt(padded || "0");
}

export function formatGen(atto: string | bigint, digits = 2): string {
  const v = typeof atto === "bigint" ? atto : BigInt(atto || "0");
  const whole = v / ATTO;
  const frac = ((v % ATTO) * BigInt(10) ** BigInt(digits)) / ATTO;
  const fracStr = frac.toString().padStart(digits, "0").replace(/0+$/, "");
  return fracStr ? `${whole}.${fracStr}` : whole.toString();
}

export function shortAddr(a: string): string {
  return a ? `${a.slice(0, 6)}…${a.slice(-4)}` : "";
}
