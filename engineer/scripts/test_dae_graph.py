import os
import re
import unittest

import dae_resolve
import dae_graph

GOOD = """\
feature: 012-x
segments:
  - name: front
    checkpoints: [2, 3, 4]
    nodes:
      - id: acs
        cp: 2
        shape: chain
      - id: panel
        cp: 2
        shape: star
        model: frontier
        verified_by: human
  - name: middle
    checkpoints: [5, 6, 7]
    nodes:
      - id: green
        cp: 5
        shape: loop
        max_rounds: 12
        no_progress: stuck_loop_threshold
      - id: refine
        cp: 6
        shape: diamond
        verified_by: tool
"""


def _errors(text):
    return dae_graph.check(dae_resolve.read_manifest(text))


class GraphCheckTests(unittest.TestCase):
    def test_good_graph_passes(self):
        self.assertEqual(_errors(GOOD), [])

    def test_loop_without_cap_fails(self):
        out = _errors(GOOD.replace("        max_rounds: 12\n", ""))
        self.assertTrue(any("max_rounds" in e for e in out), out)

    def test_loop_without_no_progress_fails(self):
        out = _errors(GOOD.replace("        no_progress: stuck_loop_threshold\n", ""))
        self.assertTrue(any("no_progress" in e for e in out), out)

    def test_fan_out_verified_by_judgment_fails(self):
        out = _errors(GOOD.replace("verified_by: tool", "verified_by: judgment"))
        self.assertTrue(any("outside the fan-out" in e for e in out), out)

    def test_segment_spanning_front_gate_fails(self):
        out = _errors(GOOD.replace("[2, 3, 4]", "[2, 3, 4, 5]"))
        self.assertTrue(any("spans a human gate" in e for e in out), out)

    def test_product_model_name_fails(self):
        out = _errors(GOOD.replace("model: frontier", "model: opus"))
        self.assertTrue(any("not a class" in e for e in out), out)

    def test_node_outside_its_segment_fails(self):
        out = _errors(GOOD.replace("        cp: 6\n", "        cp: 8\n"))
        self.assertTrue(any("not in the segment" in e for e in out), out)

    def test_per_checkpoint_front_splits_after_cp2(self):
        text = "front: per-checkpoint\n" + GOOD
        out = _errors(text)
        self.assertTrue(any("spans a human gate" in e for e in out), out)

    def test_middle_runs_through_cp8(self):
        self.assertEqual(_errors(GOOD.replace("[5, 6, 7]", "[5, 6, 7, 8]")), [])

    def test_yield_of_unknown_parent_fails(self):
        out = _errors(GOOD.replace("        shape: star\n",
                                   "        shape: star\n        yield_of: nope\n"))
        self.assertTrue(any("yield_of" in e for e in out), out)

    def test_malformed_graph_reports_instead_of_crashing(self):
        self.assertTrue(_errors("segments:\n  - name: x\n    checkpoints: [2]\n"
                                "    nodes:\n      - just-a-string\n"))

    def test_frontier_loop_fails(self):
        out = _errors(GOOD.replace("        max_rounds: 12\n",
                                   "        max_rounds: 12\n        model: frontier\n"))
        self.assertTrue(any("frontier on a loop" in e for e in out), out)

    def test_coordinator_doc_example_is_valid(self):
        doc = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "references", "coordinator.md")
        with open(doc, encoding="utf-8") as f:
            example = re.search(r"```yaml\n(feature:.*?)```", f.read(), re.S).group(1)
        self.assertEqual(_errors(example), [])


if __name__ == "__main__":
    unittest.main()
