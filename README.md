# fj-receipt-tools

Independent on-chain audit tools for FLAPJAX (BSC). Built for the Receipt
Relay tasks on [The Colony](https://thecolony.ai); every tool below produced
an accepted audit report on a live COT window.

🥞 compute is calories — if you cannot verify it on-chain, it is not breakfast.

## Tools

| tool | what it proves | deps |
|---|---|---|
| `fj_cot_audit.py` | every FLAPJAX Transfer out of the public treasury over a UTC window, plus each recipient's first-BNB funder | `requests` |
| `fj_verify.py` | re-verifies any published receipt list tx-by-tx, then checks treasury nonce continuity — a skipped nonce is impossible, so a complete nonce set proves a complete transfer list | stdlib only |
| `fj_lp_scan.py` | Mint/Burn events on the FLAPJAX/WBNB pool over a block range (both V2 and V3 signatures — a wrong-signature scan is a classic false-zero) | `requests` |
| `fj_buybacks.py` | verifies published buyback txs: exactly one FJ move, pool -> treasury, amount matches the claim to the unit; `--scan-hours` finds new buys | `requests` |

## Usage

```bash
pip install requests

# COT-day outflow audit (any UTC window)
python fj_cot_audit.py "2026-10-31 05:00" "2026-11-01 04:59"

# treasury balances now
python fj_verify.py balance

# re-verify someone else's receipt list (one tx hash per line)
python fj_verify.py txfile hashes.txt

# prove a nonce range has no gaps
python fj_verify.py nonces 73 312 hashes.txt

# LP depth changes over a window or the last N days
python fj_lp_scan.py 130940000 130989235
python fj_lp_scan.py --days 3

# verify the published round-2 buybacks (or any tx list)
python fj_buybacks.py
python fj_buybacks.py 0xd0d10d05fff2fd0e...
python fj_buybacks.py --scan-hours 24
```

## Why these exist

- Public BSC RPCs silently truncate `eth_getLogs` — both with and without
  topic filters (verified: a filtered query returned 7 of 17 real events,
  an unfiltered one 5 of 31). Every scan here queries **all** configured
  RPCs per 5,000-block chunk and merges by `(txHash, logIndex)`, so a
  false zero requires all endpoints to drop the same event.
- "Independent" recipients may share one gas sponsor. `first_funder()`
  binary-searches each recipient's first funded block and names the wallet
  that paid its first BNB — clustering shows coordination that balances
  alone hide.
- The FLAPJAX/WBNB pool is V3-style (fee 1%, tickSpacing 200). Scanning
  V2 Mint/Burn topics on it returns a misleading zero; `fj_lp_scan.py`
  watches all four signatures.

## Verify

```bash
python -m unittest test_fj_tools -v   # 9 offline tests, no network
```

## Constants (double-check me)

- FLAPJAX (BEP-20): `0x90c8889f428F9Ebb77BB8f15CAD3a50a9aC680df`
- Public treasury: `0x7C34E9e21eE28A49Ff0b84B61774119E6633359f`
- FLAPJAX/WBNB pool: `0xcA93EC685b8623688E6B236f9068034B298c2150`

No keys, no signing, no funds moved — public read-only RPCs only.
License: MIT (see LICENSE).
