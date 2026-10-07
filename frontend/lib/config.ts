// Studio Next (chain 61997). The contract address comes from the deploy script
// via frontend/.env.local (NEXT_PUBLIC_ODDSX_CONTRACT_ADDRESS).
export const CHAIN_ID = 61997;
export const CHAIN_ID_HEX = "0xf22d";
export const RPC_URL =
  process.env.NEXT_PUBLIC_GENLAYER_RPC_URL ?? "https://studio-next.genlayer.com/api";
export const EXPLORER_URL = "https://explorer-studio-next.genlayer.com";
export const CONTRACT_ADDRESS = (process.env.NEXT_PUBLIC_ODDSX_CONTRACT_ADDRESS ?? "") as `0x${string}`;

export const ATTO = BigInt("1000000000000000000");
export const CHALLENGE_WINDOW_SECONDS = 24 * 60 * 60;
