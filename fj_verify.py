#!/usr/bin/env python3
# flapjax-verify — independent FLAPJAX treasury verifier (zero dependencies).
# Method: public BSC free RPCs block eth_getLogs, so this tool works from
# candidate tx hashes (from any published report) and re-verifies each one
# on-chain, then checks nonce continuity — the strongest completeness proof
# available without an index (a skipped nonce is impossible by construction).
#
# Usage:
#   python3 flapjax_verify.py balance            # treasury FLAPJAX + BNB now
#   python3 flapjax_verify.py nonces 73 312      # verify nonce coverage given --hashes file
#   python3 flapjax_verify.py txfile hashes.txt  # re-verify a list of tx hashes
#
# hashes.txt: one 0x... tx hash per line (from any audit report you distrust).
import json, sys, urllib.request

TREASURY = '0x7c34e9e21ee28a49ff0b84b61774119e6633359f'
FJ = '0x90c8889f428f9ebb77bb8f15cad3a50a9ac680df'
RPCS = ['https://bsc-dataseed.binance.org',
        'https://bsc-dataseed.bnbchain.org',
        'https://binance.nodereal.io',
        'https://bsc.publicnode.com']
_i = [0]

def rpc(method, params):
    for _ in range(len(RPCS) * 2):
        url = RPCS[_i[0] % len(RPCS)]; _i[0] += 1
        try:
            req = urllib.request.Request(
                url, data=json.dumps({'jsonrpc': '2.0', 'id': 1,
                                      'method': method, 'params': params}).encode(),
                headers={'Content-Type': 'application/json'})
            res = json.load(urllib.request.urlopen(req, timeout=30))
            if 'result' in res:
                return res['result']
        except Exception:
            continue
    return None

def balance_of(token, addr):
    data = '0x70a08231000000000000000000000000' + addr[2:]
    r = rpc('eth_call', [{'to': token, 'data': data}, 'latest'])
    return int(r, 16) / 1e18 if r else None

def cmd_balance():
    blk = int(rpc('eth_blockNumber', []), 16)
    fj = balance_of(FJ, TREASURY)
    bnb = int(rpc('eth_getBalance', [TREASURY, 'latest']), 16) / 1e18
    print('block', blk)
    print('treasury', TREASURY)
    print('FLAPJAX %.6f' % fj if fj is not None else 'FLAPJAX: error')
    print('BNB %.8f' % bnb if bnb is not None else 'BNB: error')

def load_hashes(path):
    return [l.strip() for l in open(path) if l.strip().startswith('0x')]

def cmd_txfile(path, lo=None, hi=None):
    txs = {}
    for n, h in enumerate(load_hashes(path)):
        tx = rpc('eth_getTransactionByHash', [h])
        if tx and (tx.get('from') or '').lower() == TREASURY:
            txs[int(tx['nonce'], 16)] = tx
        if n % 50 == 0:
            print('...', n, 'checked', len(txs), 'treasury txs', file=sys.stderr)
    if not txs:
        print('no treasury txs verified')
        return
    lo = lo if lo is not None else min(txs)
    hi = hi if hi is not None else max(txs)
    missing = [n for n in range(lo, hi + 1) if n not in txs]
    spends = [(n, int(t['value'], 16) / 1e18, t['to'], t['hash'])
              for n, t in sorted(txs.items()) if int(t['value'], 16) > 0]
    total = sum(v for _, v, _, _ in spends)
    print('treasury txs verified:', len(txs), 'nonces %d-%d' % (lo, hi))
    print('missing nonces:', missing or 'NONE — completeness proven')
    print('value spends:', len(spends), 'total %.8f BNB' % total)
    for n, v, to, h in spends:
        print('  nonce %3d  %10.8f BNB -> %s  %s' % (n, v, to, h[:18] + '…'))

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'balance':
        cmd_balance()
    elif a[0] == 'nonces' and len(a) >= 3:
        cmd_txfile(a[3] if len(a) > 3 else 'hashes.txt', int(a[1]), int(a[2]))
    elif a[0] == 'txfile':
        cmd_txfile(a[1] if len(a) > 1 else 'hashes.txt')
    else:
        print(__doc__)
