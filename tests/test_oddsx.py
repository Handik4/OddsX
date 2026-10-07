"""Direct-mode tests for the OddsX Clearinghouse contract.

Run: /Users/ehs4n/Westphalia/.venv/bin/python -m pytest -q   (any env with gltest)
Direct mode executes the leader function only; validator logic is covered by
integration runs against a live network.
"""

import json
import time
from datetime import datetime, timezone

CONTRACT = "contracts/oddsx_market.py"
ATTO = 10**18
BOND = 10 * ATTO
DAY = 24 * 60 * 60
SOURCES = ["https://news.example/ruling", "https://court.example/opinion"]


def llm(direct_vm, round_marker, verdict, trace):
    payload = json.dumps({"verdict": verdict, "reasoning_trace": trace})
    direct_vm.mock_llm(rf".*Round: {round_marker}.*", json.dumps(payload))


def mock_sources(direct_vm):
    direct_vm.mock_web(r".*news\.example.*", {"status": 200, "body": "The court found the clause void."})
    direct_vm.mock_web(r".*court\.example.*", {"status": 200, "body": "Opinion: clause 4 violates term X."})


def warp(direct_vm, seconds):
    later = datetime.fromtimestamp(time.time() + seconds, tz=timezone.utc)
    direct_vm.warp(later.strftime("%Y-%m-%dT%H:%M:%SZ"))


def fund(direct_vm, who, amount=1000 * ATTO):
    direct_vm.deal(who, amount)


def hex_of(c, direct_vm, who):
    direct_vm.sender = who
    return c.whoami()


def make_market(c, direct_vm, creator, resolves_in=3600):
    direct_vm.sender = creator
    return c.create_market(
        "Did the ruling violate term X?",
        "Resolves YES if the cited opinion finds a violation of term X.",
        SOURCES,
        int(time.time()) + resolves_in,
    )


def bet(c, direct_vm, who, mid, side, gen):
    fund(direct_vm, who)
    direct_vm.sender = who
    direct_vm.value = gen * ATTO
    c.place_bet(mid, side)
    direct_vm.value = 0


def resolved_market(c, direct_vm, alice, bob, verdict="YES"):
    """Market with Alice on YES and Bob on NO, resolved at Layer 1."""
    mock_sources(direct_vm)
    mid = make_market(c, direct_vm, alice)
    bet(c, direct_vm, alice, mid, "YES", 100)
    bet(c, direct_vm, bob, mid, "NO", 100)
    warp(direct_vm, 7200)
    llm(direct_vm, "LAYER 1", verdict, "Source 1 and 2 agree the clause was void.")
    direct_vm.sender = alice
    c.resolve_market(mid)
    return mid


def test_market_creation_and_state(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mid = make_market(c, direct_vm, direct_alice)
    assert mid == 1
    assert c.get_market_count() == 1
    m = c.get_market(mid)
    assert m["status"] == "OPEN"
    assert m["resolution_sources"] == SOURCES
    assert m["yes_pool"] == "0" and m["no_pool"] == "0"
    assert m["verdict"] == "" and m["reasoning_trace"] == ""


def test_market_creation_validation(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    future = int(time.time()) + 3600
    with direct_vm.expect_revert("[EXPECTED]"):
        c.create_market("", "d", SOURCES, future)
    with direct_vm.expect_revert("[EXPECTED]"):
        c.create_market("t", "d", [], future)
    with direct_vm.expect_revert("[EXPECTED]"):
        c.create_market("t", "d", ["ftp://bad"], future)
    with direct_vm.expect_revert("[EXPECTED]"):
        c.create_market("t", "d", SOURCES, int(time.time()) - 10)


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
    with direct_vm.expect_revert("[EXPECTED]"):
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


def test_layer1_resolution_stores_verdict_and_trace(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    m = c.get_market(mid)
    assert m["status"] == "RESOLVED"
    assert m["verdict"] == "YES"
    assert "LAYER 1" in m["reasoning_trace"]
    assert SOURCES[0] in m["reasoning_trace"] and SOURCES[1] in m["reasoning_trace"]
    assert "clause was void" in m["reasoning_trace"]
    assert m["challenge_deadline"] == m["resolved_at"] + DAY


def test_invalid_llm_verdict_is_rejected(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    mock_sources(direct_vm)
    mid = make_market(c, direct_vm, direct_alice)
    warp(direct_vm, 7200)
    llm(direct_vm, "LAYER 1", "MAYBE", "unsure")
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("[LLM_ERROR]"):
        c.resolve_market(mid)
    assert c.get_market(mid)["status"] == "OPEN"


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
    assert c.preview_payout(mid, alice) == str(196 * ATTO)  # whole net pool
    assert c.claim_winnings(mid) == str(196 * ATTO)
    with direct_vm.expect_revert("Nothing to withdraw"):
        c.claim_winnings(mid)  # no double payout

    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_bob)) == "0"


def test_successful_challenge_overturns_and_rewards(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")  # bad Layer 1 result
    llm(direct_vm, "LAYER 3", "NO", "Audit: Layer 1 misread clause 4; the opinion upholds term X.")

    fund(direct_vm, direct_charlie)
    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    out = c.challenge_resolution(mid, "Layer 1 ignored the dissent in source 2.")
    direct_vm.value = 0

    assert out["overturned"] is True and out["verdict"] == "NO"
    m = c.get_market(mid)
    assert m["status"] == "FINAL" and m["challenged"] and m["overturned"]
    assert m["original_verdict"] == "YES" and m["verdict"] == "NO"
    assert "LAYER 3" in m["reasoning_trace"] and "LAYER 1" in m["original_trace"]
    assert m["fee_pool"] == "0"

    # Challenger: bond back + the full market fee pool (4 GEN).
    charlie = hex_of(c, direct_vm, direct_charlie)
    assert c.claimable_of(charlie) == str(BOND + 4 * ATTO)
    assert c.withdraw() == str(BOND + 4 * ATTO)

    # Bettor on the corrected side collects the whole net pool.
    bob = hex_of(c, direct_vm, direct_bob)
    assert c.preview_payout(mid, bob) == str(196 * ATTO)
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_alice)) == "0"


def test_failed_challenge_slashes_bond_to_accurate_bettors(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    llm(direct_vm, "LAYER 3", "YES", "Audit confirms Layer 1: opinion finds a violation.")

    fund(direct_vm, direct_charlie)
    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    out = c.challenge_resolution(mid, "I simply disagree.")
    direct_vm.value = 0

    assert out["overturned"] is False and out["verdict"] == "YES"
    m = c.get_market(mid)
    assert m["status"] == "FINAL" and m["bonus_pool"] == str(BOND)

    # Challenger gets nothing back; the bond is slashed.
    assert c.claimable_of(hex_of(c, direct_vm, direct_charlie)) == "0"
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("Nothing to withdraw"):
        c.withdraw()

    # The accurate bettor receives the net pool plus the slashed bond.
    alice = hex_of(c, direct_vm, direct_alice)
    assert c.preview_payout(mid, alice) == str(196 * ATTO + BOND)
    assert m["fee_pool"] == "0"  # fee pool moved to the treasury, not to the challenger

    # A settled market cannot be challenged a second time.
    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    with direct_vm.expect_revert("not in a challengeable state"):
        c.challenge_resolution(mid, "again")
    direct_vm.value = 0


def test_challenge_guards(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "YES")
    fund(direct_vm, direct_charlie)
    direct_vm.sender = direct_charlie
    direct_vm.value = BOND - 1
    with direct_vm.expect_revert("Challenge bond must be exactly"):
        c.challenge_resolution(mid, "short bond")
    direct_vm.value = BOND
    warp(direct_vm, 7200 + DAY + 60)
    with direct_vm.expect_revert("Challenge window has closed"):
        c.challenge_resolution(mid, "too late")
    direct_vm.value = 0


def test_inconclusive_refunds_net_stakes(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(CONTRACT)
    mid = resolved_market(c, direct_vm, direct_alice, direct_bob, "INCONCLUSIVE")
    warp(direct_vm, 7200 + DAY + 60)
    direct_vm.sender = direct_alice
    c.finalize_market(mid)
    assert c.get_market(mid)["refund_mode"] is True
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_alice)) == str(98 * ATTO)
    assert c.preview_payout(mid, hex_of(c, direct_vm, direct_bob)) == str(98 * ATTO)
