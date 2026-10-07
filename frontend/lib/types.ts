export type Verdict = "YES" | "NO" | "INCONCLUSIVE" | "";
export type ContractStatus = "OPEN" | "RESOLVED" | "FINAL";

export interface Market {
  id: number;
  creator: string;
  title: string;
  description: string;
  resolution_sources: string[];
  resolution_date: number;
  status: ContractStatus;
  yes_pool: string;
  no_pool: string;
  fee_pool: string;
  bonus_pool: string;
  verdict: Verdict;
  reasoning_trace: string;
  resolved_at: number;
  challenge_deadline: number;
  challenged: boolean;
  challenger: string;
  challenge_reason: string;
  original_verdict: Verdict;
  original_trace: string;
  overturned: boolean;
  refund_mode: boolean;
}

export interface Position {
  yes: string;
  no: string;
  settled: boolean;
}

export interface Config {
  challenge_bond: string;
  challenge_window: number;
  min_bet: string;
  fee_bps: number;
}

// Display phase derived from contract status and the clock.
export type Phase = "active" | "awaiting" | "resolved" | "final";
