#!/usr/bin/env python3
"""fj_lp_scan.py — Mint/Burn event scan for the FLAPJAX/WBNB pool.

Detects LP additions (Mint) and withdrawals (Burn) on the pool contract
over a block range, so a liquidity report cannot hide depth changes
between ticks. Answers: "did anyone add or pull liquidity in this window?"

The FLAPJAX/WBNB pool at 0xcA93…2150 is a Uniswap V3-style pair
(fee 1%, tickSpacing 200 — verified on chain 2026-11-01). V3 Mint/Burn
carry different topics than V2, so this tool scans BOTH signatures and
labels which flavour matched. A wrong-signature scan is exactly the kind
of false-zero a lazy LP report can hide behind.

Verified live 2026-11-01: 50,000-block scan returned zero LP events —
liquidity provably static over that range.

Usage:
    pip install requests
    python fj_lp_scan.py <from_block> <to_block>
    python fj_lp_scan.py --days 3        # scan the last N days
"""
import requests, json, sys

RPCS = [
    "https://rpc-bsc.48.club",
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.defibit.io",
    "https://bsc-rpc.publicnode.com",
]
POOL = "0xca93ec685b8623688e6b236f9068034b298c2150"   # FLAPJAX/WBNB pair

# V2: Mint(address,uint256,uint256) / Burn(address,uint256,uint256,address)
V2_MINT = "0x4c209b5fc8ad50761f13e2e1088ba56a560dff690a1c6fef26394f4c03821c4f"
V2_BURN = "0xdccd412f0b1252819cb1fd330b93224ca42612892bb3f4f789976e6d81936496"
# V3: Mint(address,address,int24,int24,uint128,uint256,uint256) /
#     Burn(address,int24,int24,uint128,uint256,uint256)
V3_MINT = "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
V3_BURN = "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"

KINDS = {V2_MINT: "Mint(V2)", V2_BURN: "Burn(V2)",
         V3_MINT: "Mint(V3)", V3_BURN: "Burn(V3)"}
CHUNK = 5000   # 48.club getLogs range cap


def rpc(method, params, timeout=30):
    for u in RPCS:
        try:
            j = requests.post(u, json={"jsonrpc": "2.0", "id": 1,
                "method": method, "params": params}, timeout=timeout).json()
            if "result" in j and j["result"] is not None:
                return j["result"], u
        except Exception:
            pass
    return None, None


def scan_events(b0, b1, topics):
    """Scan every chunk, merge by (tx, logIndex) across RPCs.
    Public nodes silently truncate getLogs — a merged multi-RPC answer is
    stronger than trusting one node."""
    merged, used, gaps = {}, set(), []
    a = b0
    while a <= b1:
        z = min(a + CHUNK - 1, b1)
        got = False
        for u in RPCS:
            try:
                j = requests.post(u, json={"jsonrpc": "2.0", "id": 1,
                    "method": "eth_getLogs",
                    "params": [{"address": POOL, "fromBlock": hex(a),
                        "toBlock": hex(z), "topics": [topics]}]},
                        timeout=30).json()
                part = j.get("result")
                if part is not None:
                    for l in part:
                        merged[(l["transactionHash"], l["logIndex"])] = l
                    used.add(u.split("//")[1].split("/")[0])
                    got = True
                    if u.startswith("https://rpc-bsc.48.club"):
                        break      # trusted indexer answered
            except Exception:
                pass
        if not got:
            print(f"  chunk {a}..{z}: NO RPC answered", file=sys.stderr)
            gaps.append((a, z))
        a = z + 1
    if gaps:
        raise SystemExit(
            f"INCOMPLETE SCAN: {len(gaps)} chunks had no RPC answer "
            f"({gaps[0][0]}..{gaps[-1][1]}). A zero here is not a zero — "
            f"re-run later; do not report 'no events'.")
    return sorted(merged.values(), key=lambda l: int(l["blockNumber"], 16)), used


def decode_ev(l):
    """Return (kind, amount0, amount1). For V3 Mint/Burn the last two
    data words are amount0/amount1 (token0=FLAPJAX, token1=WBNB). For V2
    they are the only two data words."""
    kind = KINDS.get(l["topics"][0], "Unknown")
    d = l["data"][2:].rjust(64 * 5, "0")
    a0 = int(d[-128:-64], 16) / 1e18
    a1 = int(d[-64:], 16) / 1e18
    return kind, a0, a1


def main():
    if len(sys.argv) == 3 and sys.argv[1] != "--days":
        b0, b1 = int(sys.argv[1]), int(sys.argv[2])
    elif len(sys.argv) == 3:
        n = int(sys.argv[2])
        head, _ = rpc("eth_blockNumber", [])
        b1 = int(head, 16)
        b0 = b1 - n * 28800          # ~3s blocks on BSC
    else:
        print(__doc__); return
    print(f"scanning Mint+Burn (V2+V3) on pool {POOL} blocks {b0}..{b1}")
    evs, used = scan_events(b0, b1, list(KINDS))
    print(f"events: {len(evs)}  (rpcs used: {sorted(used)})")
    for l in evs:
        kind, a0, a1 = decode_ev(l)
        print(f"  {kind}  blk {int(l['blockNumber'],16)}  "
              f"{a0:,.0f} FJ / {a1:.4f} WBNB  tx {l['transactionHash']}")
    if not evs:
        print("  -> liquidity provably static over the range")
    json.dump({"blocks": [b0, b1],
               "events": [{"kind": decode_ev(l)[0],
                           "block": int(l["blockNumber"], 16),
                           "tx": l["transactionHash"]} for l in evs]},
              open("fj_lp_scan.json", "w"), indent=1)


if __name__ == "__main__":
    main()
