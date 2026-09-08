# multisig-analyzer

Risk scoring helper for Safe (Gnosis Safe) multisigs.

Multisig threshold and signer identity are two of the cheapest checks to run before signing off on a DeFi vault deal, and yet most reviews skip them.

This script automates both checks. Run it on any Safe address and get a structured report in 5 seconds.

## What it does

Given a Safe multisig address and chain, the script pulls:

1. **Owners and threshold** from the Safe Transaction Service API
2. **ENS reverse names** for each signer (identity disclosure proxy)
3. **Two risk scores:**
   - **Threshold ratio** = threshold / total owners. Below 0.5 means a minority subset can move funds. 0.5 to 2/3 is moderate. Above 2/3 is supermajority required.
   - **Identity disclosure rate** = signers with on-chain ENS / total. Below 0.2 means anonymous multisig, single phishing event drains it.

Each score returns a flag (ok / watch / high_risk) and a human-readable note. The script aggregates both into an `overall_flag` and a list of recommended actions.

## Install

Python 3.10+. One dependency:

```bash
pip install requests
```

## Usage

```bash
python multisig_analyzer.py 0x9Df30AFb9F11d54a59c0096Fc12dF80E64B167C2
```

Other chains:

```bash
python multisig_analyzer.py 0xabc... --chain arbitrum
python multisig_analyzer.py 0xabc... --chain optimism
python multisig_analyzer.py 0xabc... --chain base
python multisig_analyzer.py 0xabc... --chain polygon
```

Write JSON to file:

```bash
python multisig_analyzer.py 0xabc... --out reports/protocol.json
```

## Sample output

Run on MakerDAO Pause Proxy (Ethereum mainnet):

```json
{
  "address": "0x...",
  "chain": "ethereum",
  "owners_count": 8,
  "threshold": 5,
  "signers": [
    {"address": "0x123...", "ens": "vote.makerdao.eth"},
    {"address": "0x456...", "ens": ""}
  ],
  "threshold_score": {
    "ratio": 0.625,
    "flag": "watch",
    "note": "simple majority, moderate collusion risk if signers are correlated"
  },
  "identity_score": {
    "disclosed": 5,
    "total": 8,
    "rate": 0.625,
    "flag": "ok",
    "note": "majority of signers have public on-chain identity"
  },
  "summary": {
    "overall_flag": "watch",
    "actions": [
      "threshold ratio 0.625: simple majority, moderate collusion risk if signers are correlated. escalate to protocol team before deploying capital."
    ]
  }
}
```

## What this does NOT check

This is the first layer. The full multisig DD also requires:

- **Emergency pause holder identity:** who can freeze deposits? Same multisig or separate?
- **Token upgrade keys:** is the contract upgradeable? By whom?
- **Treasury timelock:** can the multisig drain treasury instantly, or is there a delay window?
- **Governance forum quorum gaming:** is the on-chain multisig backed by real community governance, or by a Discord whitelist?

I cover all of these in my DD memos. This script just shortcuts the first 15 minutes.

## Limitations

- Only works for **Gnosis Safe** multisigs. Custom multisig contracts (1 of 1 admin keys, Aragon DAOs, etc.) are not supported.
- ENS reverse resolution is best-effort. A signer without ENS may still be a public team member identified through other channels (Twitter, Github, audits).
- This is a heuristic. A 7-of-7 multisig with all signers from the same team is not safer than a 3-of-5 with external advisors. Always overlay context.

## Roadmap

- Aragon DAO + DAOhaus support
- Cross-chain multisig comparison (same protocol, different deployments)
- Historical signer rotation tracking
- Integration with audit reports to cross-check what signers control

## License

MIT. Use freely in your own DD pipelines.

