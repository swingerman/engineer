import unittest

import dae_lifecycle


class RunOfferTests(unittest.TestCase):
    def _offering(self):
        return {lc["id"]: [s["id"] for s in lc["stages"] if dae_lifecycle.RUN in s["skills"]]
                for lc in dae_lifecycle.lifecycles()}

    def test_every_feature_checkpoint_offers_the_coordinator(self):
        offering = self._offering()
        for lc in ("feature", "prototype"):
            self.assertTrue({"1.5", "2", "3", "4", "5", "6", "7", "8"} <= set(offering[lc]), lc)

    def test_express_and_fix_never_offer_it(self):
        offering = self._offering()
        self.assertEqual(offering["express"], [])
        self.assertEqual(offering["fix"], [])


if __name__ == "__main__":
    unittest.main()
