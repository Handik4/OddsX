export type Verdict = "YES" | "NO" | "INCONCLUSIVE" | "";
export type ContractStatus = "OPEN" | "RESOLVED" | "FINAL";

export interface Market {
  id: number;
  creator: string;
  title: string;
  description: string;
  resolution_sources: string[];
  resolution_date: number;
  expiry_deadline: number;
  status: ContractStatus;
  yes_pool: string;
  no_pool: string;
  fee_pool: string;
  bonus_pool: string;
  creator_stake: string;
  challenge_bond: string;
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
  expired: boolean;
}

export interface Position {
  yes: string;
  no: string;
  settled: boolean;
}

export interface Config {
  creator_stake: string;
  min_challenge_bond: string;
  challenge_bond_bps: number;
  challenge_window: number;
  expiry_grace: number;
  min_bet: string;
  fee_bps: number;
}

// Display phase derived from contract status and the clock.
export type Phase = "active" | "awaiting" | "resolved" | "final";
