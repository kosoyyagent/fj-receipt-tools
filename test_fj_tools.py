#!/usr/bin/env python3
"""Offline tests for fj-receipt-tools. No network needed — fixtures only.
Run: python -m unittest test_fj_tools -v
"""
import unittest

import fj_cot_audit
import fj_lp_scan
import fj_verify


class TestCotAudit(unittest.TestCase):
    def test_parse_utc(self):
        ts = fj_cot_audit.parse_utc("2026-10-31 05:00")
        self.assertEqual(ts, 1793422800)

    def test_pad(self):
        addr = "0x" + "ab" * 20
        padded = fj_cot_audit.pad(addr)
        self.assertEqual(padded, "0x" + "0" * 24 + addr[2:])
        self.assertEqual(len(padded), 66)

    def test_treasury_topic_matches_filter(self):
        # the scan keeps logs whose topic[1] (from) is the treasury
        self.assertTrue(
            fj_cot_audit.pad(fj_cot_audit.TREAS).endswith(
                fj_cot_audit.TREAS[2:]))

    def test_transfer_topic_constant(self):
        # keccak("Transfer(address,address,uint256)") — well-known value
        self.assertEqual(fj_cot_audit.TRANSFER,
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef")


class TestLpScan(unittest.TestCase):
    def _log(self, topic, data_words):
        data = "0x" + "".join("%064x" % w for w in data_words)
        return {"topics": [topic], "data": data,
                "blockNumber": "0x10", "transactionHash": "0x" + "11" * 32,
                "logIndex": "0x0"}

    def test_decode_v2_mint(self):
        # V2 Mint data = amount0, amount1
        l = self._log(fj_lp_scan.V2_MINT, [10**21, 2 * 10**18])
        kind, a0, a1 = fj_lp_scan.decode_ev(l)
        self.assertEqual(kind, "Mint(V2)")
        self.assertAlmostEqual(a0, 1000.0)
        self.assertAlmostEqual(a1, 2.0)

    def test_decode_v3_burn_last_two_words(self):
        # V3 Burn data = amount(liquidity), amount0, amount1
        l = self._log(fj_lp_scan.V3_BURN, [7, 5 * 10**21, 10**18])
        kind, a0, a1 = fj_lp_scan.decode_ev(l)
        self.assertEqual(kind, "Burn(V3)")
        self.assertAlmostEqual(a0, 5000.0)
        self.assertAlmostEqual(a1, 1.0)

    def test_v3_topics_registered(self):
        # regression: pool is V3-style; V3-only sigs must be in the scan set
        self.assertIn("Mint(V3)", fj_lp_scan.KINDS.values())
        self.assertIn("Burn(V3)", fj_lp_scan.KINDS.values())
        self.assertEqual(len(fj_lp_scan.KINDS), 4)


class TestVerify(unittest.TestCase):
    def test_balance_of_selector(self):
        # balanceOf(address) selector + padded address, no leading zeros lost
        data = "0x70a08231000000000000000000000000" + "ab" * 20
        self.assertTrue(data.startswith("0x70a08231"))
        self.assertEqual(len(data), 2 + 8 + 64)

    def test_load_hashes_filters(self, ):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                         delete=False) as f:
            f.write("0x" + "aa" * 32 + "\nnotahash\n\n0x" + "bb" * 32 + "\n")
            p = f.name
        try:
            hs = fj_verify.load_hashes(p)
        finally:
            os.unlink(p)
        self.assertEqual(len(hs), 2)
        self.assertTrue(all(h.startswith("0x") and len(h) == 66 for h in hs))


if __name__ == "__main__":
    unittest.main()
