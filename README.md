# OddsX Clearinghouse

A subjective prediction market clearinghouse on GenLayer. Polymarket-style markets work when the answer is a number or a score. They break when the answer needs judgment: *did this ruling violate term X? did this DAO vote breach its charter?* A token-holder oracle settles those questions by who holds the most tokens. OddsX settles them with GenLayer validators that read the sources, reason, and publish their reasoning on-chain.

- Contract: `contracts/oddsx_market.py` (GenVM, `genvm-lint check` clean)
- Tests: `tests/test_oddsx.py` (direct mode, 11 tests)
- Deploy + seed: `scripts/deploy.py`
- Dashboard: `frontend/` (Next.js + Tailwind, light mode only, live against Studio Next, chain 61997)

## How a market works

1. **Create.** Anyone creates a market with a title, resolution criteria, 1–5 source URLs and a resolution date.
2. **Bet.** Until the resolution date, users bet YES or NO with native GEN. A 2% fee on every bet goes to the market's fee pool. The remaining net stake goes to the YES or NO pool.
3. **Resolve (Layer 1).** After the date, anyone calls `resolve_market`.
4. **Challenge window.** The market sits in `RESOLVED` for 24 hours.
5. **Finalize and claim.** With no challenge, `finalize_market` closes it. Winners split the whole net pool pro rata. Winners claim with `claim_winnings`.

If the verdict is `INCONCLUSIVE`, or nobody backed the winning side, the market refunds net stakes (the fee is not refunded).

## The Reasoning Trace replaces the biased oracle

`resolve_market` runs a non-deterministic block (`gl.vm.run_nondet`):

- The **leader** fetches every resolution source, builds a prompt that fences the source text as untrusted data, and asks an LLM for strict JSON: `{"verdict": "YES" | "NO" | "INCONCLUSIVE", "reasoning_trace": "..."}`.
- The contract prepends a deterministic source ledger (each URL, its number, and whether it was fetched). The result is stored on-chain as the market's `reasoning_trace`.
- Each **validator** re-runs the whole pipeline independently. It accepts the leader only if it reaches the same verdict. Free-text reasoning is allowed to differ, because two honest analysts rarely use the same words. A leader that returns malformed LLM output or an invalid verdict is rejected, which forces a new leader.

Nobody holds a special vote. The outcome is whatever independent validators, each with their own model and their own fetch of the sources, agree on. Anyone can read the verdict *and why*, with the exact sources cited, in the dashboard's trace viewer.

## Layered escalation game theory

| Layer | Who acts | Cost | What happens |
|---|---|---|---|
| 1. Fast resolution | Anyone | Gas only | Multi-validator consensus on verdict + trace |
| 2. Bond challenge | Anyone, within 24h | 10 GEN bond (exact) | Challenger stakes a heavy bond to contest Layer 1 |
| 3. Schelling settlement | Validators | Paid by the challenger's bond at risk | A deeper adversarial trace audits the Layer 1 reasoning |

Layer 3 re-reads the sources and receives the Layer 1 trace and the challenger's argument, all fenced as untrusted. It is told to re-derive the verdict independently and to depart from Layer 1 only when the sources support it. The Layer 3 result is final.

**Payoffs**

- **Overturned** (Layer 3 verdict differs from Layer 1): the challenger gets the 10 GEN bond back plus the market's whole fee pool. Bettors on the corrected side collect the net pool.
- **Upheld** (same verdict): the bond is slashed and added to the pool paid to bettors on the accurate side. The fee pool goes to the protocol treasury.
- **Unchallenged:** the fee pool goes to the treasury.

**Why this is incentive-compatible.** A challenge costs 10 GEN and only pays when the first verdict was actually wrong, so frivolous challenges lose money. A wrong Layer 1 verdict is profitable to challenge, so lazy or manipulated first rounds get corrected. Validators converge on the answer the sources best support, because that is the answer an independent validator will reach (a Schelling point). The bond is fixed rather than scaled, which keeps the hackathon scope simple. A production version would scale it to the pool size.

## Contract surface

Views: `get_market_count`, `get_config`, `get_market`, `get_position`, `preview_payout`, `claimable_of`, `whoami`.

Writes: `create_market`, `place_bet` (payable), `resolve_market`, `challenge_resolution` (payable, exactly the bond), `finalize_market`, `claim_winnings`, `withdraw`.

Amounts are atto-GEN (10^18). Errors use the prefixes `[EXPECTED]`, `[EXTERNAL]`, `[TRANSIENT]` and `[LLM_ERROR]`. Settlement credits a pull balance and then queues a native transfer.

## Run it

```bash
# lint
genvm-lint check contracts/oddsx_market.py

# tests (any environment with gltest + pytest installed)
python -m pytest -q

# deploy to Studio Next and seed two demo markets (a mock legal ruling and a mock DAO dispute)
DEPLOYER_PRIVATE_KEY=0x... python scripts/deploy.py   # or omit the key for a funded throwaway account
# writes deployments/studio-next.json and frontend/.env.local

# dashboard
cd frontend && npm install && npm run dev      # package.json uses port 3200
```

The dashboard connects an injected wallet (MetaMask) and switches it to Studio Next (chain ID 61997, added automatically if missing). Reads work without a wallet.

## Limits worth knowing

- Direct-mode tests run the leader only. Validator agreement is exercised on a live network, not in `tests/`.
- Validators are paid through GenLayer's fee system, not by this contract. "Accurate verifiers" in this contract means the bettors on the accurate side.
- The demo markets use public pages as stand-ins, so their verdicts are illustrative.
