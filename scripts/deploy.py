"""Deploy OddsX Clearinghouse to GenLayer Studio Next and seed two demo markets.

Usage (any environment with genlayer-py installed):

    DEPLOYER_PRIVATE_KEY=0x... python scripts/deploy.py     # use your own key
    python scripts/deploy.py                                # throwaway funded account

The throwaway path only works on Studio networks, where accounts can be funded
through the simulator. The deployed address is written to
deployments/studio-next.json and frontend/.env.local.
"""

import json
import os
import time
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studio_devnet

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "oddsx_market.py"
RPC_URL = os.environ.get("GENLAYER_RPC_URL", "https://studio-next.genlayer.com/api")
EXPLORER_URL = "https://explorer-studio-next.genlayer.com"
FUNDING = 1000 * 10**18
CREATOR_STAKE = 5 * 10**18  # create_market is payable and requires exactly this stake
WAIT_RETRIES = 200
WAIT_INTERVAL_MS = 3000

# Sources are public pages that exist today; the "ruling" and "governance"
# scenarios are fictional and phrased so validators weigh the sources subjectively.
DEMO_MARKETS = [
    {
        "title": "Did the Meridian v. Halcyon ruling violate the fair-use clause of the Digital Works Act?",
        "description": (
            "Mock legal ruling. Resolves YES if the published opinion finds that the defendant's "
            "transformative use exceeded the fair-use exception in Section 107 as interpreted by "
            "the court. Resolves NO if the court upholds the use as fair. INCONCLUSIVE if the "
            "sources do not state a finding."
        ),
        "sources": [
            "https://en.wikipedia.org/wiki/Fair_use",
            "https://www.law.cornell.edu/uscode/text/17/107",
        ],
        "days": 3,
    },
    {
        "title": "Was the Aurora DAO treasury proposal AIP-17 executed in breach of its own governance charter?",
        "description": (
            "Mock DAO governance dispute. Resolves YES if the governance records show the proposal "
            "bypassed the quorum or timelock required by the charter. Resolves NO if every "
            "procedural requirement was met. INCONCLUSIVE if the records are missing or contradictory."
        ),
        "sources": [
            "https://en.wikipedia.org/wiki/Decentralized_autonomous_organization",
            "https://en.wikipedia.org/wiki/Quorum",
        ],
        "days": 5,
    },
]


def fees_for(client):
    return client.estimate_transaction_fees()


def wait(client, tx_hash):
    return client.wait_for_transaction_receipt(
        transaction_hash=tx_hash,
        interval=WAIT_INTERVAL_MS,
        retries=WAIT_RETRIES,
    )


def contract_address_of(receipt) -> str:
    candidates = [
        (receipt.get("data") or {}).get("contract_address"),
        (receipt.get("txDataDecoded") or {}).get("contractAddress"),
        receipt.get("to_address"),
        receipt.get("recipient"),
    ]
    for value in candidates:
        if value:
            return value
    raise RuntimeError(f"No contract address in receipt: {receipt}")


def main() -> None:
    key = os.environ.get("DEPLOYER_PRIVATE_KEY")
    account = create_account(key) if key else create_account()
    client = create_client(chain=studio_devnet, endpoint=RPC_URL, account=account)
    print(f"Deployer: {account.address}")

    if not key:
        client.fund_account(account.address, FUNDING)
        print("Funded throwaway account on Studio.")

    code = CONTRACT_PATH.read_text()
    tx = client.deploy_contract(code=code, account=account, args=[], fees=fees_for(client))
    receipt = wait(client, tx)
    address = contract_address_of(receipt)
    print(f"Deployed OddsX Clearinghouse at {address}")

    for spec in DEMO_MARKETS:
        resolution_date = int(time.time()) + spec["days"] * 86400
        tx = client.write_contract(
            address=address,
            function_name="create_market",
            account=account,
            args=[spec["title"], spec["description"], spec["sources"], resolution_date],
            value=CREATOR_STAKE,
            fees=fees_for(client),
        )
        wait(client, tx)
        print(f"Seeded market: {spec['title'][:60]}...")

    count = client.read_contract(address=address, function_name="get_market_count", args=[])
    print(f"Markets on-chain: {count}")

    record = {
        "network": "studio-next",
        "chain_id": 61997,
        "rpc_url": RPC_URL,
        "contract_address": address,
        "explorer_url": f"{EXPLORER_URL}/address/{address}",
        "source": "contracts/oddsx_market.py",
        "deployer": account.address,
    }
    out = ROOT / "deployments"
    out.mkdir(exist_ok=True)
    (out / "studio-next.json").write_text(json.dumps(record, indent=2) + "\n")
    frontend = ROOT / "frontend"
    if frontend.exists():
        (frontend / ".env.local").write_text(
            f"NEXT_PUBLIC_ODDSX_CONTRACT_ADDRESS={address}\n"
            f"NEXT_PUBLIC_GENLAYER_RPC_URL={RPC_URL}\n"
        )
        print("Wrote frontend/.env.local")


if __name__ == "__main__":
    main()
