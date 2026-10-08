"""Direct-mode tests for the OddsX Clearinghouse contract.

Run: /Users/ehs4n/Westphalia/.venv/bin/python -m pytest -q   (any env with gltest)

Direct mode runs the leader function inline. Validator behaviour is tested
through direct_vm.run_validator(), which replays the validator closure captured
from the last run_nondet call against the current mocks.
"""

import json
import time
from datetime import datetime, timezone

import pytest

CONTRACT = "contracts/oddsx_market.py"
ATTO = 10**18
STAKE = 5 * ATTO
MIN_BOND = 5 * ATTO
DAY = 24 * 60 * 60
CID_A = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
CID_B = "QmT78zSuBmuS4z925WZfrqQ1qHaJ56DQaTfyMUF7F8ff5o"
CID_V1 = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
SOURCES = [f"ipfs://{CID_A}", f"ipfs://{CID_B}/opinion.txt"]


# ------------------------------------------------------------------ helpers
def llm(direct_vm, round_marker, verdict, trace="Sources agree on the outcome."):
    """Mock the LLM for one round. The pattern also requires the resolution date
    line, so a prompt that omits the date does not match and the call fails."""
    payload = json.dumps({"verdict": verdict, "reasoning_trace": trace})
    direct_vm.mock_llm(
        rf"(?s).*Round: {round_marker}.*Resolution date: \d{{4}}-\d{{2}}-\d{{2}} .*", json.dumps(payload)
    )


def mock_sources(direct_vm):
    direct_vm.mock_web(rf".*{CID_A}.*", {"status": 200, "body": "The court found the clause void."})
    direct_vm.mock_web(rf".*{CID_B}.*", {"status": 200, "body": "Opinion: clause 4 violates term X."})


def warp(direct_vm, seconds):
    later = datetime.fromtimestamp(time.time() + seconds, tz=timezone.utc)
    direct_vm.warp(later.strftime("%Y-%m-%dT%H:%M:%SZ"))


def fund(direct_vm, who, amount=100_000 * ATTO):
    direct_vm.deal(who, amount)


def hex_of(c, direct_vm, who):
    direct_vm.sender = who
    return c.whoami()


def make_market(c, direct_vm, creator, resolves_in=3600, sources=None):
    fund(direct_vm, creator)
    direct_vm.sender = creator
    direct_vm.value = STAKE
    mid = c.create_market(
        "Did the ruling violate term X?",
        "Resolves YES if the cited opinion finds a violation of term X.",
        sources or SOURCES,
        int(time.time()) + resolves_in,
    )
    direct_vm.value = 0
    return mid


def bet(c, direct_vm, who, mid, side, gen=None, wei=None):
    fund(direct_vm, who)
    direct_vm.sender = who
    direct_vm.value = wei if wei is not None else gen * ATTO
    c.place_bet(mid, side)
    direct_vm.value = 0


def resolve(c, direct_vm, mid, caller, verdict, trace="Source 1 and 2 agree the clause was void."):
    mock_sources(direct_vm)
    warp(direct_vm, 7200)
    llm(direct_vm, "LAYER 1", verdict, trace)
    direct_vm.sender = caller
    return c.resolve_market(mid)


def resolved_market(c, direct_vm, alice, bob, verdict="YES"):
    """Market created by Alice: Alice 100 GEN on YES, Bob 100 GEN on NO, resolved at Layer 1."""
    mid = make_market(c, direct_vm, alice)
    bet(c, direct_vm, alice, mid, "YES", 100)
    bet(c, direct_vm, bob, mid, "NO", 100)
    resolve(c, direct_vm, mid, alice, verdict)
    return mid


def challenge(c, direct_vm, who, mid, reason="The verdict is wrong."):
    bond = int(c.get_challenge_bond(mid))
    fund(direct_vm, who)
    direct_vm.sender = who
    direct_vm.value = bond
    out = c.challenge_resolution(mid, reason)
    direct_vm.value = 0
    return out, bond


def treasury_balance(c, direct_vm):
    return int(c.claimable_of(c.get_treasury()))


# ------------------------------------------------------- creation and state
def test_market_creation_and_state(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    assert mid == 1 and c.get_market_count() == 1
    m = c.get_market(mid)
    assert m["status"] == "OPEN"
    assert m["resolution_sources"] == SOURCES
    assert m["yes_pool"] == "0" and m["no_pool"] == "0"
    assert m["verdict"] == "" and m["reasoning_trace"] == ""
    assert m["creator_stake"] == str(STAKE)
    assert m["expiry_deadline"] == m["resolution_date"] + 7 * DAY


def test_market_creation_validation(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    fund(direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = STAKE
    future = int(time.time()) + 3600
    with direct_vm.expect_revert("Title must be"):
        c.create_market("", "d", SOURCES, future)
    with direct_vm.expect_revert("Provide 1-5 resolution sources"):
        c.create_market("t", "d", [], future)
    with direct_vm.expect_revert("Provide 1-5 resolution sources"):
        c.create_market("t", "d", [f"ipfs://{CID_A}"] * 6, future)
    with direct_vm.expect_revert("Description exceeds"):
        c.create_market("t", "x" * 1001, SOURCES, future)
    with direct_vm.expect_revert("Source URL exceeds"):
        c.create_market("t", "d", [f"ipfs://{CID_A}/" + "p" * 200], future)
    with direct_vm.expect_revert("future"):
        c.create_market("t", "d", SOURCES, int(time.time()) - 10)


def test_creator_stake_must_be_exact(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    fund(direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    future = int(time.time()) + 3600
    for wrong in (0, STAKE - 1, STAKE + 1):
        direct_vm.value = wrong
        with direct_vm.expect_revert("Creator stake must be exactly"):
            c.create_market("t", "d", SOURCES, future)
    direct_vm.value = 0
    assert c.get_market_count() == 0


# --------------------------------------------------------------------- SSRF
SAFE_URLS = [
    f"ipfs://{CID_A}",
    f"ipfs://{CID_B}/opinion.txt",
    f"ipfs://{CID_V1}",
    f"https://ipfs.io/ipfs/{CID_A}",
    f"https://dweb.link/ipfs/{CID_V1}/doc/ruling.json",
]
UNSAFE_URLS = [
    "https://news.example/ruling",
    "http://court.example/opinion?id=1",
    "https://en.wikipedia.org/wiki/Fair_use",
    "https://8.8.8.8/status",
    "http://localhost/admin",
    "http://127.0.0.1/",
    "http://169.254.169.254/latest/meta-data",
    "http://user:pass@example.com/",
    f"http://ipfs.io/ipfs/{CID_A}",  # plain http gateway
    f"https://evil.example/ipfs/{CID_A}",  # untrusted gateway could serve mutable bytes
    f"https://ipfs.io.evil.example/ipfs/{CID_A}",
    f"https://user@ipfs.io/ipfs/{CID_A}",
    "ipfs://notacid",
    "ipfs://Qm123",
    f"ipfs://{CID_A}\\x",
    f"ipfs://{CID_A} ",
    f"ipns://{CID_A}",
    "ftp://example.com/file",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "example.com/no-scheme",
    "",
]


@pytest.mark.parametrize("url", SAFE_URLS)
def test_ssrf_filter_accepts_public_urls(direct_vm, direct_deploy, url):
    c = direct_deploy(CONTRACT)
    assert c.is_safe_url(url) is True


@pytest.mark.parametrize("url", UNSAFE_URLS)
def test_ssrf_filter_rejects_internal_targets(direct_vm, direct_deploy, url):
    c = direct_deploy(CONTRACT)
    assert c.is_safe_url(url) is False


def test_create_market_rejects_unsafe_source(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    fund(direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    direct_vm.value = STAKE
    future = int(time.time()) + 3600
    for bad in ("https://news.example/ruling", "http://court.example/opinion", "http://127.0.0.1:8545/", "file:///etc/passwd"):
        with direct_vm.expect_revert("Unsafe or unsupported source URL"):
            c.create_market("t", "d", [SOURCES[0], bad], future)
    direct_vm.value = 0
    assert c.get_market_count() == 0


# ------------------------------------------------------------------ betting
def test_betting_pools_and_fee(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, mid, "YES", 100)
    bet(c, direct_vm, direct_bob, mid, "NO", 50)
    m = c.get_market(mid)
    assert m["yes_pool"] == str(98 * ATTO)  # 2% fee skimmed into the fee pool
    assert m["no_pool"] == str(49 * ATTO)
    assert m["fee_pool"] == str(3 * ATTO)
    pos = c.get_position(mid, hex_of(c, direct_vm, direct_alice))
    assert pos["yes"] == str(98 * ATTO) and pos["no"] == "0"
    with direct_vm.expect_revert("Side must be YES or NO"):
        bet(c, direct_vm, direct_bob, mid, "MAYBE", 1)


def test_cannot_bet_or_resolve_at_wrong_time(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mock_sources(direct_vm)
    mid = make_market(c, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Resolution date not reached"):
        c.resolve_market(mid)
    warp(direct_vm, 7200)
    with direct_vm.expect_revert("Betting is closed"):
        bet(c, direct_vm, direct_alice, mid, "YES", 1)


# ---------------------------------------------------------- Layer 1 and LLM
def test_layer1_resolution_stores_verdict_and_trace(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    m = c.get_market(mid)
    assert m["status"] == "RESOLVED" and m["verdict"] == "YES"
    assert "LAYER 1" in m["reasoning_trace"]
    assert SOURCES[0] in m["reasoning_trace"] and SOURCES[1] in m["reasoning_trace"]
    assert "clause was void" in m["reasoning_trace"]
    assert m["challenge_deadline"] == m["resolved_at"] + DAY


def test_resolution_date_is_passed_to_the_llm(direct_vm, direct_deploy, direct_alice):
    """llm() only matches a prompt containing 'Resolution date: YYYY-MM-DD ...'.
    A prompt without the date would not match and resolve_market would fail."""
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    out = resolve(c, direct_vm, mid, direct_alice, "NO")
    assert out["verdict"] == "NO"


def test_invalid_llm_verdict_is_rejected(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    mock_sources(direct_vm)
    warp(direct_vm, 7200)
    llm(direct_vm, "LAYER 1", "MAYBE", "unsure")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("[LLM_ERROR]"):
        c.resolve_market(mid)
    assert c.get_market(mid)["status"] == "OPEN"


def test_reasoning_trace_is_truncated_before_storage(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    resolve(c, direct_vm, mid, direct_alice, "YES", trace="Because. " * 2000)
    trace = c.get_market(mid)["reasoning_trace"]
    reasoning = trace.split("\n", 1)[1]
    assert len(reasoning) <= 1000
    assert len(trace) < 1000 + 600  # layer label plus the two-source ledger


def test_unsafe_source_is_never_fetched_at_resolution(direct_vm, direct_deploy, direct_alice):
    """Defense in depth: even if a bad URL were somehow stored, the fetch step
    refuses it. Simulated by calling the module helper directly."""
    import sys

    direct_deploy(CONTRACT)
    module = sys.modules["_contract_oddsx_market"]
    got = module._fetch_source("https://news.example/ruling")
    assert got["ok"] is False and got["note"] == "blocked"


# ------------------------------------------------------- validator behaviour
def test_validator_agrees_on_same_verdict(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    resolve(c, direct_vm, mid, direct_alice, "YES")
    assert direct_vm.run_validator() is True


def test_validator_disagrees_on_different_verdict(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    resolve(c, direct_vm, mid, direct_alice, "YES")
    direct_vm.clear_mocks()
    mock_sources(direct_vm)
    llm(direct_vm, "LAYER 1", "NO", "A different reading of the sources.")
    assert direct_vm.run_validator() is False


def test_validator_accepts_different_wording_same_verdict(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    resolve(c, direct_vm, mid, direct_alice, "YES", trace="First phrasing of the reasoning.")
    direct_vm.clear_mocks()
    mock_sources(direct_vm)
    llm(direct_vm, "LAYER 1", "YES", "Completely different phrasing of the reasoning.")
    assert direct_vm.run_validator() is True


def test_validator_rejects_malformed_leader_output(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    resolve(c, direct_vm, mid, direct_alice, "YES")
    assert direct_vm.run_validator(leader_result={"verdict": "MAYBE", "reasoning_trace": "x"}) is False
    assert direct_vm.run_validator(leader_result={"verdict": "YES", "reasoning_trace": ""}) is False
    assert direct_vm.run_validator(leader_result="not a dict") is False


def test_validator_rejects_leader_llm_error_but_accepts_matching_transient(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    resolve(c, direct_vm, mid, direct_alice, "YES")
    # Leader failed with an LLM error while the validator succeeds -> disagree.
    assert direct_vm.run_validator(leader_error=Exception("[LLM_ERROR] garbage")) is False
    # Both sides hit a transient source failure -> agree.
    direct_vm.clear_mocks()
    direct_vm.mock_web(r".*", {"status": 503, "body": ""})
    assert direct_vm.run_validator(leader_error=Exception("[TRANSIENT] source down")) is True


# ------------------------------------------------- finalization and payouts
def test_unchallenged_market_finalizes_and_pays_winner(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Challenge window still open"):
        c.finalize_market(mid)
    warp(direct_vm, 7200 + DAY + 60)
    assert c.finalize_market(mid) == "YES"
    m = c.get_market(mid)
    assert m["status"] == "FINAL" and not m["challenged"]

    alice = hex_of(c, direct_vm, direct_alice)
    assert c.preview_payout(mid, alice) == str(196 * ATTO)
    # Alice is the creator and the winner: winnings plus the refunded creator stake.
    assert c.claim_winnings(mid) == str(196 * ATTO + STAKE)
    with direct_vm.expect_revert("Nothing to withdraw"):
        c.claim_winnings(mid)  # no double payout
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_bob)) == "0"
    # Fee pool (4 GEN) went to the treasury, with zero division dust.
    assert treasury_balance(c, direct_vm) == 4 * ATTO


def test_division_dust_is_routed_to_the_treasury(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_bob, mid, "YES", wei=10**17 + 7)
    bet(c, direct_vm, direct_charlie, mid, "YES", wei=10**17 + 13)
    bet(c, direct_vm, direct_alice, mid, "NO", wei=10**17 + 1)
    resolve(c, direct_vm, mid, direct_alice, "YES")
    warp(direct_vm, 7200 + DAY + 60)
    direct_vm.sender = direct_alice
    c.finalize_market(mid)
    m = c.get_market(mid)
    total = int(m["yes_pool"]) + int(m["no_pool"])
    fee_to_treasury = int(m["fee_pool"])  # zeroed at finalization
    assert fee_to_treasury == 0

    before = treasury_balance(c, direct_vm)
    direct_vm.sender = direct_bob
    paid_bob = int(c.claim_winnings(mid))
    assert treasury_balance(c, direct_vm) == before  # dust waits for the last winner
    direct_vm.sender = direct_charlie
    paid_charlie = int(c.claim_winnings(mid))
    dust = treasury_balance(c, direct_vm) - before
    assert dust >= 0
    assert paid_bob + paid_charlie + dust == total  # nothing is lost or locked


# --------------------------------------------------------- Layer 2 and 3
def test_dynamic_challenge_bond_scales_with_pool(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    small = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, small, "YES", 1)
    assert c.get_challenge_bond(small) == str(MIN_BOND)  # floor at 5 GEN

    big = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, big, "YES", 1000)
    bet(c, direct_vm, direct_bob, big, "NO", 1000)
    pool = int(c.get_market(big)["yes_pool"]) + int(c.get_market(big)["no_pool"])
    assert c.get_challenge_bond(big) == str(pool * 5 // 100)  # 5% of the pool
    assert int(c.get_challenge_bond(big)) == 98 * ATTO
    assert c.get_market(big)["challenge_bond"] == c.get_challenge_bond(big)


def test_challenger_profit_is_min_of_fee_pool_and_half_bond(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """Overturn pays the bond back plus min(fee_pool, bond // 2); the rest of the
    fee pool goes to the treasury. Large market: bond 98 GEN, fee pool 40 GEN."""
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, mid, "YES", 1000)
    bet(c, direct_vm, direct_bob, mid, "NO", 1000)
    resolve(c, direct_vm, mid, direct_alice, "YES")
    fee_pool = int(c.get_market(mid)["fee_pool"])  # 40 GEN
    llm(direct_vm, "LAYER 3", "NO", "Audit overturns the verdict.")
    out, bond = challenge(c, direct_vm, direct_charlie, mid)
    assert out["overturned"] is True and bond == 98 * ATTO
    profit = min(fee_pool, bond // 2)
    assert profit == fee_pool == 40 * ATTO
    charlie = hex_of(c, direct_vm, direct_charlie)
    assert int(c.claimable_of(charlie)) == bond + profit
    # Treasury: the remainder of the fee pool (zero here) plus the slashed creator stake.
    assert treasury_balance(c, direct_vm) == (fee_pool - profit) + STAKE // 2


def test_challenger_profit_formula_in_a_small_market(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, mid, "YES", 3)
    bet(c, direct_vm, direct_bob, mid, "NO", 3)
    resolve(c, direct_vm, mid, direct_alice, "YES")
    fee_pool = int(c.get_market(mid)["fee_pool"])
    llm(direct_vm, "LAYER 3", "NO", "Audit overturns the verdict.")
    _, bond = challenge(c, direct_vm, direct_charlie, mid)
    assert bond == MIN_BOND
    profit = min(fee_pool, bond // 2)
    assert int(c.claimable_of(hex_of(c, direct_vm, direct_charlie))) == bond + profit
    assert treasury_balance(c, direct_vm) == (fee_pool - profit) + STAKE // 2


def test_successful_challenge_overturns_and_rewards(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")  # bad Layer 1 result
    llm(direct_vm, "LAYER 3", "NO", "Audit: Layer 1 misread clause 4; the opinion upholds term X.")
    out, bond = challenge(c, direct_vm, direct_charlie, mid, "Layer 1 ignored the dissent in source 2.")
    assert bond == 196 * ATTO * 5 // 100  # 9.8 GEN

    assert out["overturned"] is True and out["verdict"] == "NO"
    m = c.get_market(mid)
    assert m["status"] == "FINAL" and m["challenged"] and m["overturned"]
    assert m["original_verdict"] == "YES" and m["verdict"] == "NO"
    assert "LAYER 3" in m["reasoning_trace"] and "LAYER 1" in m["original_trace"]
    assert m["fee_pool"] == "0"

    # Challenger: bond back + min(fee_pool, bond // 2) = min(4, 4.9) = 4 GEN of profit.
    charlie = hex_of(c, direct_vm, direct_charlie)
    assert c.claimable_of(charlie) == str(bond + 4 * ATTO)
    assert c.withdraw() == str(bond + 4 * ATTO)
    # The creator provided a source set that led to a wrong verdict: half the stake slashed to the treasury, half refunded.
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == str(STAKE - STAKE // 2)
    assert treasury_balance(c, direct_vm) == STAKE // 2

    # Bettor on the corrected side collects the whole net pool.
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_bob)) == str(196 * ATTO)
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_alice)) == "0"


def test_failed_challenge_slashes_bond_to_accurate_bettors(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    llm(direct_vm, "LAYER 3", "YES", "Audit confirms Layer 1: opinion finds a violation.")
    out, bond = challenge(c, direct_vm, direct_charlie, mid, "I simply disagree.")

    assert out["overturned"] is False and out["verdict"] == "YES"
    m = c.get_market(mid)
    assert m["status"] == "FINAL" and m["bonus_pool"] == str(bond) and not m["refund_mode"]

    # The challenger gets nothing back; the bond is slashed.
    assert c.claimable_of(hex_of(c, direct_vm, direct_charlie)) == "0"
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("Nothing to withdraw"):
        c.withdraw()

    # The accurate bettor receives the net pool plus the slashed bond.
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_alice)) == str(196 * ATTO + bond)
    assert treasury_balance(c, direct_vm) == 4 * ATTO  # the whole fee pool
    # The verdict survived the challenge, so the creator stake is refunded.
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == str(STAKE)

    # A settled market cannot be challenged a second time.
    direct_vm.sender = direct_charlie
    direct_vm.value = bond
    with direct_vm.expect_revert("not in a challengeable state"):
        c.challenge_resolution(mid, "again")
    direct_vm.value = 0


def test_challenge_guards(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    bond = int(c.get_challenge_bond(mid))
    fund(direct_vm, direct_charlie)
    direct_vm.sender = direct_charlie
    for wrong in (bond - 1, bond + 1, MIN_BOND):  # the old fixed 10 GEN bond is also wrong now
        direct_vm.value = wrong
        with direct_vm.expect_revert("Challenge bond must be exactly"):
            c.challenge_resolution(mid, "wrong bond")
    direct_vm.value = bond
    warp(direct_vm, 7200 + DAY + 60)
    with direct_vm.expect_revert("Challenge window has closed"):
        c.challenge_resolution(mid, "too late")
    direct_vm.value = 0


# ------------------------------------------------ treasury routing, refunds
def test_inconclusive_refunds_stakes_and_slashes_creator_stake(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "INCONCLUSIVE")
    warp(direct_vm, 7200 + DAY + 60)
    direct_vm.sender = direct_alice
    c.finalize_market(mid)
    assert c.get_market(mid)["refund_mode"] is True
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_alice)) == str(98 * ATTO)
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_bob)) == str(98 * ATTO)
    # Creator stake (5 GEN) is slashed to the treasury together with the 4 GEN fee pool.
    assert treasury_balance(c, direct_vm) == STAKE + 4 * ATTO
    # The creator gets only the refunded bet back, not the stake.
    assert c.claim_winnings(mid) == str(98 * ATTO)


def test_creator_stake_is_refunded_on_a_normal_resolution(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "NO")
    warp(direct_vm, 7200 + DAY + 60)
    direct_vm.sender = direct_alice
    c.finalize_market(mid)
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == str(STAKE)
    assert treasury_balance(c, direct_vm) == 4 * ATTO


def test_slashed_bond_is_routed_to_treasury_when_market_is_inconclusive(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """Layer 1 and Layer 3 both say INCONCLUSIVE: the bond is slashed, but there
    are no winners to receive it, so it must go to the treasury, not stay locked."""
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "INCONCLUSIVE")
    llm(direct_vm, "LAYER 3", "INCONCLUSIVE", "Audit also finds the sources insufficient.")
    out, bond = challenge(c, direct_vm, direct_charlie, mid)
    assert out["overturned"] is False
    m = c.get_market(mid)
    assert m["refund_mode"] is True and m["bonus_pool"] == "0"
    assert treasury_balance(c, direct_vm) == bond + STAKE + 4 * ATTO  # bond + slashed stake + fee pool


def test_slashed_bond_is_routed_to_treasury_when_winning_side_is_empty(
    direct_vm, direct_deploy, direct_alice, direct_charlie
):
    """Everyone bet YES, the verdict is NO and survives a challenge: nobody holds
    the winning side. Stakes are refunded and the bond goes to the treasury."""
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, mid, "YES", 100)
    resolve(c, direct_vm, mid, direct_alice, "NO")
    llm(direct_vm, "LAYER 3", "NO", "Audit confirms NO.")
    out, bond = challenge(c, direct_vm, direct_charlie, mid)
    m = c.get_market(mid)
    assert out["overturned"] is False
    assert m["refund_mode"] is True and m["bonus_pool"] == "0"
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_alice)) == str(98 * ATTO)
    # Verdict is NO (a normal resolution), so the creator stake is refunded, not slashed.
    assert treasury_balance(c, direct_vm) == bond + 2 * ATTO


# ----------------------------------------------------------- stuck markets
def test_refund_expired_unsticks_a_market_that_cannot_resolve(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, mid, "YES", 100)
    bet(c, direct_vm, direct_bob, mid, "NO", 100)

    # Dead sources: every Layer 1 attempt fails, so the market stays OPEN.
    direct_vm.mock_web(r".*", {"status": 503, "body": ""})
    warp(direct_vm, 3600 + 60)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("[TRANSIENT]"):
        c.resolve_market(mid)
    assert c.get_market(mid)["status"] == "OPEN"

    # Still inside the 7 day grace period: cannot be expired yet.
    warp(direct_vm, 3600 + 6 * DAY)
    with direct_vm.expect_revert("has not expired yet"):
        c.refund_expired(mid)

    # After the grace period anyone can force an INCONCLUSIVE resolution.
    warp(direct_vm, 3600 + 7 * DAY + 60)
    out = c.refund_expired(mid)
    assert out["verdict"] == "INCONCLUSIVE"
    m = c.get_market(mid)
    assert m["status"] == "RESOLVED" and m["verdict"] == "INCONCLUSIVE"
    assert "EXPIRED" in m["reasoning_trace"] and m["expired"] is True

    with direct_vm.expect_revert("Market is not open"):
        c.refund_expired(mid)  # only works once

    # After the challenge window it finalizes into refunds; the creator stake is slashed.
    warp(direct_vm, 3600 + 7 * DAY + 60 + DAY + 60)
    c.finalize_market(mid)
    assert c.get_market(mid)["refund_mode"] is True
    assert c.claim_winnings(mid) == str(98 * ATTO)  # Bob gets his net stake back
    direct_vm.sender = direct_alice
    assert c.claim_winnings(mid) == str(98 * ATTO)
    assert treasury_balance(c, direct_vm) == STAKE + 4 * ATTO


def test_refund_expired_is_rejected_for_resolved_markets(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    warp(direct_vm, 3600 + 8 * DAY)
    with direct_vm.expect_revert("Market is not open"):
        c.refund_expired(mid)


# ---------------------------------------------------- creator stake rules
def test_creator_stake_is_half_slashed_when_a_challenge_overturns_the_verdict(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == "0"  # held until finalization
    llm(direct_vm, "LAYER 3", "NO", "Overturned.")
    challenge(c, direct_vm, direct_charlie, mid)
    assert c.get_market(mid)["overturned"] is True
    # Half the stake is slashed to the treasury, the other half goes back to the creator.
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == str(STAKE // 2)
    assert treasury_balance(c, direct_vm) == STAKE // 2  # whole fee pool went to the challenger


def test_creator_stake_is_refunded_when_a_challenge_is_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "NO")
    llm(direct_vm, "LAYER 3", "NO", "Upheld.")
    challenge(c, direct_vm, direct_charlie, mid)
    assert c.get_market(mid)["overturned"] is False
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == str(STAKE)


def test_creator_stake_is_held_until_finalization(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")  # RESOLVED, in the challenge window
    assert c.get_market(mid)["status"] == "RESOLVED"
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == "0"
    assert treasury_balance(c, direct_vm) == 0


def test_creator_stake_is_slashed_on_timeout_even_if_the_market_later_resolves_yes(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    """A creator cannot cancel for free by breaking their URLs. Even when a
    challenge then rescues the expired market into a YES verdict, the stake is
    slashed exactly once."""
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    bet(c, direct_vm, direct_alice, mid, "YES", 100)
    bet(c, direct_vm, direct_bob, mid, "NO", 100)
    warp(direct_vm, 3600 + 7 * DAY + 60)
    direct_vm.sender = direct_bob
    c.refund_expired(mid)
    mock_sources(direct_vm)
    llm(direct_vm, "LAYER 3", "YES", "Sources were readable after all.")
    out, bond = challenge(c, direct_vm, direct_charlie, mid)
    assert out["overturned"] is True and out["verdict"] == "YES"
    assert c.claimable_of(hex_of(c, direct_vm, direct_alice)) == "0"
    assert treasury_balance(c, direct_vm) == STAKE  # slashed once; fee pool went to the challenger


# ------------------------------------------------------ exact accounting
def _addr(hex_str):
    return bytes.fromhex(hex_str[2:])


def settle_everyone(c, direct_vm, participants, mid):
    """Every participant claims, then the treasury withdraws. Returns the total
    paid out and asserts nothing is left claimable or unreachable."""
    total_out = 0
    for who in participants:
        key = hex_of(c, direct_vm, who)
        if int(c.preview_payout(mid, key)) > 0 or int(c.claimable_of(key)) > 0:
            direct_vm.sender = who
            total_out += int(c.claim_winnings(mid))
    treasury = c.get_treasury()
    amount = int(c.claimable_of(treasury))
    if amount > 0:
        direct_vm.sender = _addr(treasury)
        total_out += int(c.withdraw())
    for who in participants:
        assert c.claimable_of(hex_of(c, direct_vm, who)) == "0"
    assert c.claimable_of(treasury) == "0"
    return total_out


def finalize_after_window(c, direct_vm, caller, mid, base_seconds):
    warp(direct_vm, base_seconds + DAY + 60)
    direct_vm.sender = caller
    c.finalize_market(mid)


def scenario_unchallenged_yes(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    bet(c, vm, b, mid, "NO", 60)
    resolve(c, vm, mid, a, "YES")
    finalize_after_window(c, vm, a, mid, 7200)
    return mid, STAKE + 160 * ATTO


def scenario_overturned(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    bet(c, vm, b, mid, "NO", 100)
    resolve(c, vm, mid, a, "YES")
    llm(vm, "LAYER 3", "NO", "Overturned.")
    _, bond = challenge(c, vm, ch, mid)
    return mid, STAKE + 200 * ATTO + bond


def scenario_upheld(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    bet(c, vm, b, mid, "NO", 100)
    resolve(c, vm, mid, a, "YES")
    llm(vm, "LAYER 3", "YES", "Upheld.")
    _, bond = challenge(c, vm, ch, mid)
    return mid, STAKE + 200 * ATTO + bond


def scenario_inconclusive(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    bet(c, vm, b, mid, "NO", 100)
    resolve(c, vm, mid, a, "INCONCLUSIVE")
    finalize_after_window(c, vm, a, mid, 7200)
    return mid, STAKE + 200 * ATTO


def scenario_double_inconclusive(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    bet(c, vm, b, mid, "NO", 100)
    resolve(c, vm, mid, a, "INCONCLUSIVE")
    llm(vm, "LAYER 3", "INCONCLUSIVE", "Still insufficient.")
    _, bond = challenge(c, vm, ch, mid)
    return mid, STAKE + 200 * ATTO + bond


def scenario_empty_winning_side(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    resolve(c, vm, mid, a, "NO")
    llm(vm, "LAYER 3", "NO", "Upheld.")
    _, bond = challenge(c, vm, ch, mid)
    return mid, STAKE + 100 * ATTO + bond


def scenario_expired(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    bet(c, vm, b, mid, "NO", 100)
    warp(vm, 3600 + 7 * DAY + 60)
    vm.sender = b
    c.refund_expired(mid)
    finalize_after_window(c, vm, b, mid, 3600 + 7 * DAY + 60)
    return mid, STAKE + 200 * ATTO


def scenario_expired_then_overturned(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, a, mid, "YES", 100)
    bet(c, vm, b, mid, "NO", 100)
    warp(vm, 3600 + 7 * DAY + 60)
    vm.sender = b
    c.refund_expired(mid)
    mock_sources(vm)
    llm(vm, "LAYER 3", "YES", "Readable after all.")
    _, bond = challenge(c, vm, ch, mid)
    return mid, STAKE + 200 * ATTO + bond


def scenario_odd_wei_dust(c, vm, a, b, ch):
    mid = make_market(c, vm, a)
    bet(c, vm, b, mid, "YES", wei=10**17 + 7)
    bet(c, vm, ch, mid, "YES", wei=10**17 + 13)
    bet(c, vm, a, mid, "NO", wei=10**17 + 1)
    resolve(c, vm, mid, a, "YES")
    finalize_after_window(c, vm, a, mid, 7200)
    return mid, STAKE + (10**17 + 7) + (10**17 + 13) + (10**17 + 1)


SCENARIOS = [
    scenario_unchallenged_yes,
    scenario_overturned,
    scenario_upheld,
    scenario_inconclusive,
    scenario_double_inconclusive,
    scenario_empty_winning_side,
    scenario_expired,
    scenario_expired_then_overturned,
    scenario_odd_wei_dust,
]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda f: f.__name__)
def test_total_deposits_exactly_equal_total_payouts(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, scenario
):
    """Zero wei difference: everything deposited (creator stake, bets, challenge
    bond) is paid out exactly once to participants and the treasury."""
    c = direct_deploy(CONTRACT)
    treasury = c.get_treasury()
    participants = [direct_alice, direct_bob, direct_charlie]
    assert all(hex_of(c, direct_vm, p).lower() != treasury.lower() for p in participants)
    mid, deposits = scenario(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    assert c.get_market(mid)["status"] == "FINAL"
    assert settle_everyone(c, direct_vm, participants, mid) == deposits
