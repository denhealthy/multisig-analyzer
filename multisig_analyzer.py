"""
multisig_analyzer.py

Quick risk scoring for Safe (Gnosis Safe) multisigs.

Pulls signer set and threshold from Safe Transaction Service.
Resolves ENS names for each signer.
Returns a structured risk report with two scores:
  1. threshold_ratio  threshold / owners
  2. identity_score   share of signers with on-chain identity

Usage:
    python multisig_analyzer.py 0x849D52316331967b6fF1198e5E32A0eB168D039d
    python multisig_analyzer.py 0xabc... --chain arbitrum

Supported chains:
    ethereum, arbitrum, optimism, base, polygon

Author: Denis Chaplinskii
Repo: https://github.com/denhealthy/multisig-analyzer
License: MIT
"""

import sys
import json
import argparse
from typing import Dict, List, Any

import requests


SAFE_TX_API = {
    "ethereum": "https://safe-transaction-mainnet.safe.global/api/v1",
    "arbitrum": "https://safe-transaction-arbitrum.safe.global/api/v1",
    "optimism": "https://safe-transaction-optimism.safe.global/api/v1",
    "base": "https://safe-transaction-base.safe.global/api/v1",
    "polygon": "https://safe-transaction-polygon.safe.global/api/v1",
}

ENS_REVERSE_API = "https://api.ensideas.com/ens/resolve"


def get_safe_info(address: str, chain: str) -> Dict[str, Any]:
    base = SAFE_TX_API.get(chain)
    if not base:
        raise ValueError(f"unsupported chain: {chain}. supported: {list(SAFE_TX_API)}")
    url = f"{base}/safes/{address}/"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def resolve_ens(address: str) -> str:
    try:
        r = requests.get(f"{ENS_REVERSE_API}/{address}", timeout=5)
        if r.ok:
            data = r.json()
            return data.get("name") or ""
    except requests.RequestException:
        pass
    return ""


def score_threshold_ratio(threshold: int, owners: int) -> Dict[str, Any]:
    ratio = threshold / owners if owners else 0
    if ratio >= 2 / 3:
        flag = "ok"
        note = "supermajority required, low collusion risk"
    elif ratio >= 0.5:
        flag = "watch"
        note = "simple majority, moderate collusion risk if signers are correlated"
    else:
        flag = "high_risk"
        note = "below half, a minority subset can move funds unilaterally"
    return {"ratio": round(ratio, 3), "flag": flag, "note": note}


def score_identity_disclosure(signers: List[Dict[str, str]]) -> Dict[str, Any]:
    with_ens = sum(1 for s in signers if s.get("ens"))
    total = len(signers)
    rate = with_ens / total if total else 0
    if rate >= 0.6:
        flag = "ok"
        note = "majority of signers have public on-chain identity"
    elif rate >= 0.2:
        flag = "watch"
        note = "partial identity disclosure, request team to publish signer affiliations"
    else:
        flag = "high_risk"
        note = "anonymous signers, single phishing event can compromise the multisig"
    return {
        "disclosed": with_ens,
        "total": total,
        "rate": round(rate, 3),
        "flag": flag,
        "note": note,
    }


def worst_flag(flags: List[str]) -> str:
    if "high_risk" in flags:
        return "high_risk"
    if "watch" in flags:
        return "watch"
    return "ok"


def format_actions(t_score: Dict, i_score: Dict) -> List[str]:
    actions = []
    if t_score["flag"] != "ok":
        actions.append(
            f"threshold ratio {t_score['ratio']}: {t_score['note']}. "
            "escalate to protocol team before deploying capital."
        )
    if i_score["flag"] != "ok":
        actions.append(
            f"identity disclosure {i_score['rate']}: {i_score['note']}."
        )
    if not actions:
        actions.append("multisig structure passes baseline checks. proceed to the next risk layer (timelock, upgrade keys, treasury controls).")
    return actions


def analyze(address: str, chain: str = "ethereum") -> Dict[str, Any]:
    info = get_safe_info(address, chain)
    owners = info.get("owners", [])
    threshold = info.get("threshold", 0)

    signers: List[Dict[str, str]] = []
    for owner in owners:
        ens = resolve_ens(owner)
        signers.append({"address": owner, "ens": ens})

    threshold_score = score_threshold_ratio(threshold, len(owners))
    identity_score = score_identity_disclosure(signers)

    return {
        "address": address,
        "chain": chain,
        "owners_count": len(owners),
        "threshold": threshold,
        "signers": signers,
        "threshold_score": threshold_score,
        "identity_score": identity_score,
        "summary": {
            "overall_flag": worst_flag([threshold_score["flag"], identity_score["flag"]]),
            "actions": format_actions(threshold_score, identity_score),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Safe multisig risk analyzer. Returns threshold and identity scoring."
    )
    parser.add_argument("address", help="multisig contract address")
    parser.add_argument(
        "--chain",
        default="ethereum",
        choices=list(SAFE_TX_API.keys()),
        help="target chain (default ethereum)",
    )
    parser.add_argument(
        "--out",
        default="-",
        help="output file path or '-' for stdout (default stdout)",
    )
    args = parser.parse_args()

    try:
        result = analyze(args.address, args.chain)
    except requests.HTTPError as e:
        print(f"safe API error: {e}", file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        print(f"input error: {e}", file=sys.stderr)
        sys.exit(1)

    output = json.dumps(result, indent=2)
    if args.out == "-":
        print(output)
    else:
        with open(args.out, "w") as f:
            f.write(output)
        print(f"written to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
