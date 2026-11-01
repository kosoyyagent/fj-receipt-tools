#!/usr/bin/env python3
"""fj_buybacks.py — verify published FlapJax buyback txs against the chain.

Each published buyback should be exactly one FJ Transfer: pool -> treasury.
This tool fetches each tx's receipt from a public BSC RPC and checks:
  - the tx exists and succeeded
  - FJ (0x90c8…) moves from the V3 pool (0xca93…c2150) to the treasury
    (0x7C34…359f)
  - the claimed FJ amount matches the Transfer's data field to the unit
  - no FJ moves anywhere else in the same tx (no round-trips)

Usage:
    python fj_buybacks.py                        # verifies round-2 buys to date
    python fj_buybacks.py 0xTXHASH [0xTXHASH...] # verify specific txs
    python fj_buybacks.py --scan-hours 6         # find new pool->treasury sends

No keys needed — public RPC only.
"""
import requests, sys, json, datetime

RPCS = [
    "https://rpc-bsc.48.club",
    "https://bsc-rpc.publicnode.com",
]
TOK = "0x90c8889f428f9ebb77bb8f15cad3a50a9ac680df"
TREAS = "0x7c34e9e21ee28a49ff0b84b61774119e6633359f"
POOL = "0xca93ec685b8623688e6b236f9068034b298c2150"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
pad = lambda a: "0x" + "0" * 24 + a[2:]

# Published round-2 buybacks (from the Colony buyback thread, verified 11-01)
ROUND2 = {
    "2026-10-24": ("0xd0d10d05fff2fd0e898afd9ff16fb2c84d18c2d03f793eb89313e1fb326ced9b", 11647298.14928724520234397),
    "2026-10-26": ("0xa52c8d9f53c89bb6c0b02a37b9ed4b5da138e925008e0c8feebf6890acb1c55f", 11644873.28965106017968609),
    "2026-10-28": ("0xa6f25856a9ce66cdf3ba4dba21bb2c19423610076db7ed7dd827d2029d1416fa", 11645860.50460386591068455),
    "2026-10-30": ("0xeb633af6048135c86deefde0825eb49ea613427a94ced94df7c99ca511332b18", 11584882.070152512805358143),
}


def rpc(method, params):
    for u in RPCS:
        try:
            j = requests.post(u, json={"jsonrpc": "2.0", "id": 1,
                "method": method, "params": params}, timeout=30).json()
            if j.get("result") is not None:
                return j["result"]
        except Exception:
            pass
    return None


def check_tx(txh, claimed_fj=None):
    rc = rpc("eth_getTransactionReceipt", [txh])
    if not rc:
        return {"tx": txh, "verdict": "NO RECEIPT"}
    ok = rc["status"] == "0x1"
    fj = [l for l in rc["logs"]
          if l["address"].lower() == TOK and l["topics"]
          and l["topics"][0].lower() == TRANSFER]
    moves = [("0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:],
              int(l["data"], 16) / 1e18) for l in fj]
    to_treasury = [m for m in moves if m[1].lower() == TREAS and m[0].lower() == POOL]
    res = {"tx": txh, "block": int(rc["blockNumber"], 16),
           "fj_moves": moves, "status": "ok" if ok else "REVERTED"}
    if len(to_treasury) == 1 and len(moves) == 1 and ok:
        amt = to_treasury[0][2]
        if claimed_fj is None or abs(amt - claimed_fj) < 0.01:
            res["verdict"] = "MATCH"
        else:
            res["verdict"] = f"AMOUNT MISMATCH chain={amt} claimed={claimed_fj}"
    else:
        res["verdict"] = f"UNEXPECTED: {len(to_treasury)} pool->treasury moves, {len(moves)} total"
    return res


def scan_recent(hours=6):
    head = int(rpc("eth_blockNumber", []), 16)
    start = head - int(hours * 8000)        # ~8k blocks/h on BSC
    logs, b = [], start
    while b <= head:
        e = min(b + 10000 - 1, head)
        r = rpc("eth_getLogs", [{"address": TOK, "fromBlock": hex(b),
            "toBlock": hex(e), "topics": [TRANSFER, pad(POOL), pad(TREAS)]}])
        if r is None:
            print(f"WARNING: chunk {b}..{e} unanswered — coverage gap")
        else:
            logs += r
        b = e + 1
    for l in logs:
        print(int(l["blockNumber"], 16), l["transactionHash"],
              f"{int(l['data'],16)/1e18:,.0f} FJ")
    if not logs:
        print("no pool->treasury transfers in window (or RPC silently empty — cross-check)")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--scan-hours":
        scan_recent(float(args[1]) if len(args) > 1 else 6)
        return
    txs = {None: (a, None) for a in args}
    jobs = txs if args else {d: v for d, v in ROUND2.items()}
    n_ok = 0
    for label, (txh, claimed) in jobs.items():
        r = check_tx(txh, claimed)
        tag = label or "?"
        print(f"{tag} | {r['verdict']} | blk {r.get('block')} | {txh[:18]}…")
        for frm, to, amt in r.get("fj_moves", []):
            print(f"    {frm[:12]}… -> {to[:12]}…  {amt:,.2f} FJ")
        if r["verdict"] == "MATCH":
            n_ok += 1
    print(f"verified {n_ok}/{len(jobs)} buys")


if __name__ == "__main__":
    main()
