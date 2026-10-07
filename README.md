# OddsX Clearinghouse

A subjective prediction market clearinghouse on GenLayer. Polymarket-style markets work when the answer is a number or a score. They break when the answer needs judgment: *did this ruling violate term X? did this DAO vote breach its charter?* A token-holder oracle settles those questions by who holds the most tokens. OddsX settles them with GenLayer validators that read the sources, reason, and publish their reasoning on-chain.

- Contract: `contracts/oddsx_market.py` (GenVM, `genvm-lint check` clean)
- Tests: `tests/test_oddsx.py` (direct mode, 74 tests including validator replays and exact accounting)
- Deploy + seed: `scripts/deploy.py`
- Dashboard: `frontend/` (Next.js + Tailwind, light mode only, live against Studio Next, chain 61997)

## How a market works

1. **Create.** Anyone creates a market with a title, resolution criteria, 1–5 source URLs and a resolution date. Creating a market is payable: the creator locks a 5 GEN stake (see below).
2. **Bet.** Until the resolution date, users bet YES or NO with native GEN. A 2% fee on every bet goes to the market's fee pool. The remaining net stake goes to the YES or NO pool.
3. **Resolve (Layer 1).** After the date, anyone calls `resolve_market`. If that keeps failing, anyone can call `refund_expired` once 7 days have passed.
4. **Challenge window.** The market sits in `RESOLVED` for 24 hours.
5. **Finalize and claim.** With no challenge, `finalize_market` closes it. Winners split the whole net pool pro rata and claim with `claim_winnings`.

If the verdict is `INCONCLUSIVE`, or nobody backed the winning side, the market refunds net stakes (the fee is not refunded).

## The Reasoning Trace replaces the biased oracle

`resolve_market` runs a non-deterministic block (`gl.vm.run_nondet`):

- The **leader** fetches every resolution source, builds a prompt that fences the source text as untrusted data, and asks an LLM for strict JSON: `{"verdict": "YES" | "NO" | "INCONCLUSIVE", "reasoning_trace": "..."}`.
- The prompt includes the market's resolution date. The model is told to judge the question as of that date, to distrust undated content or content that looks edited afterwards, and to answer `INCONCLUSIVE` if the sources cannot establish the outcome as of that date. Reasoning is sanitized and truncated to 1000 characters before it is stored. The contract prepends a deterministic source ledger (each URL, its number, and whether it was fetched). The result is stored on-chain as the market's `reasoning_trace`.
- Each **validator** re-runs the whole pipeline independently. It accepts the leader only if it reaches the same verdict. Free-text reasoning is allowed to differ, because two honest analysts rarely use the same words. A leader that returns malformed LLM output or an invalid verdict is rejected, which forces a new leader.

Nobody holds a special vote. The outcome is whatever independent validators, each with their own model and their own fetch of the sources, agree on. Anyone can read the verdict *and why*, with the exact sources cited, in the dashboard's trace viewer.

## Layered escalation game theory

| Layer | Who acts | Cost | What happens |
|---|---|---|---|
| 1. Fast resolution | Anyone | Gas only | Multi-validator consensus on verdict + trace |
| 2. Bond challenge | Anyone, within 24h | Dynamic bond (below), exact | Challenger stakes a bond to contest Layer 1 |
| 3. Single-step escalation | Validators | Paid by the challenger's bond at risk | A deeper adversarial trace audits the Layer 1 reasoning |

Layer 3 re-reads the sources and receives the Layer 1 trace and the challenger's argument, all fenced as untrusted. It is told to re-derive the verdict independently and to depart from Layer 1 only when the sources support it. The Layer 3 result is final.

**Layer 3 is a single-step escalation.** It is one additional consensus round, not a multi-round appeal tree, which keeps the hackathon scope focused. Its result is final. A production version would add further rounds with growing bonds and validator sets.

### Dynamic challenge bond

The bond is `max(5 GEN, 5% of the market pool)`, where the pool is the YES pool plus the NO pool. A fixed bond let an attacker gamble a small amount for the whole fee pool of a large market. With a bond that scales with the pool, the downside of a failed challenge grows with the size of the market, and a 5 GEN floor still stops dust challenges. The exact bond for a market is the `challenge_bond` field of `get_market` (and the `get_challenge_bond` view). Betting is closed before a challenge can start, so the bond cannot change under a challenger.

### Payoffs

- **Overturned** (Layer 3 verdict differs from Layer 1): the challenger gets the bond back plus a profit of `min(fee_pool, bond // 2)`. The remainder of the fee pool, if any, goes to the treasury. Bettors on the corrected side collect the net pool. The creator stake is slashed.
- **Upheld** (same verdict): the bond is slashed and added to the pool paid to bettors on the accurate side. The fee pool goes to the treasury. The creator stake is refunded if the verdict is YES or NO.
- **Unchallenged:** the fee pool goes to the treasury.

In practice the fee pool is the binding term in the profit formula. The fee pool is about 2% of the net pool, while half the bond is at least 2.5% of it, so an overturn pays out the whole fee pool. A challenge is still a risk: the break-even chance of overturning is roughly 70%, because the profit is about 40% of the bond. Challengers who also hold a bet on the corrected side earn more, since they share the net pool. Total deposits (creator stake, bets, bond) always equal total payouts to the wei, which the test suite checks across nine settlement scenarios.

### Creator stake

`create_market` requires exactly 5 GEN. The stake is **held until finalization** and then either refunded or slashed in full to the treasury.

Slashed when:

1. the market resolves `INCONCLUSIVE` (unreachable, contradictory or unusable sources);
2. a challenge **overturns** the first verdict (the creator's sources led validators to a wrong result);
3. the market **times out** and `refund_expired` is called. This holds even if a later challenge rescues the expired market into a YES or NO verdict. The stake is slashed once, never twice.

Refunded only when the market finalizes normally with a YES or NO verdict, either unchallenged or with the challenge rejected.

This makes it costly to use definitive but biased sources the creator controls, and it removes the free exit of deliberately breaking a URL to force a cancellation.

### Treasury routing

The treasury is the deployer address. Anything that has no eligible recipient goes there rather than staying locked:

- the slashed challenge bond (`bonus_pool`) when the market ends in refund mode (INCONCLUSIVE verdict, or nobody backed the winning side);
- the unpaid share of the fee pool after a challenge reward;
- the creator stake of a market that is `INCONCLUSIVE`, overturned or expired;
- integer-division dust. Winner payouts round down. When the last winning stake has been claimed, the difference between the pool and what was paid out is credited to the treasury. Winners who never claim keep their share unclaimed.

The treasury withdraws with `withdraw`, like any other balance.

### Stuck markets

If `resolve_market` cannot succeed (dead URLs, no consensus), the market would stay `OPEN` and lock stakes. After `resolution_date + 7 days`, anyone can call `refund_expired(market_id)`. It moves an `OPEN` market to `RESOLVED` with an `INCONCLUSIVE` verdict. The normal challenge window and finalization follow, bettors get their net stakes back, and the creator stake is slashed.

### SSRF protection

`create_market` rejects any source URL that is not a plain `http` or `https` URL with a public host. Rejected: other schemes (`file`, `ftp`, `gopher`, `javascript`), embedded credentials, backslashes and whitespace, IPv6 literals, `localhost` and `.localhost`, `.local`, `.internal` and cloud metadata hostnames, DNS-rebinding resolvers such as `nip.io`, and IPv4 in any encoding (dotted, decimal, hex, octal, short form) when it falls in `0.0.0.0/8`, `127.0.0.0/8`, `10.0.0.0/8`, `100.64.0.0/10`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16` (including `169.254.169.254`), or multicast and reserved space. The same check runs again before every fetch. URLs are limited to 200 characters, titles to 200, descriptions to 1000, and challenge arguments to 1000. 
**SSRF filtering is strictly name-based. It does not resolve DNS (e.g., `localtest.me`) or follow redirects to block internal IPs.**

## Contract surface

Views: `get_market_count`, `get_config`, `get_market`, `get_challenge_bond`, `get_position`, `preview_payout`, `claimable_of`, `get_treasury`, `is_safe_url`, `whoami`.

Writes: `create_market` (payable, exactly the creator stake), `place_bet` (payable), `resolve_market`, `refund_expired`, `challenge_resolution` (payable, exactly the dynamic bond), `finalize_market`, `claim_winnings`, `withdraw`.

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

- **SSRF filtering is strictly name-based.** It does not resolve DNS (e.g., `localtest.me`) or follow redirects to block internal IPs.
- **Evidence snapshotting.** Source content is not snapshotted at the time of resolution. Layer 3 challenges re-fetch the live URL, which could theoretically be altered. Production deployment would require IPFS hashing of the payload.
- Direct-mode tests run the leader inline. Validator acceptance and rejection are tested by replaying the captured validator against mocks (`direct_vm.run_validator`), but real multi-validator consensus is only exercised on a live network.
- Validators are paid through GenLayer's fee system, not by this contract. "Accurate verifiers" in this contract means the bettors on the accurate side.
- The demo markets use public pages as stand-ins, so their verdicts are illustrative.
