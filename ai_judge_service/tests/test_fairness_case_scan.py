from __future__ import annotations

import unittest

from app.applications.fairness_case_scan import collect_fairness_case_items


class FairnessCaseScanTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_should_respect_scan_limit_and_keep_total_count(self) -> None:
        pages = {
            0: {"count": 10, "items": [{"caseId": 1}, {"caseId": 2}]},
            2: {"count": 10, "items": [{"caseId": 3}, {"caseId": 4}]},
            4: {"count": 10, "items": [{"caseId": 5}]},
        }

        async def fetch_page(offset: int, limit: int) -> dict:
            self.assertGreaterEqual(limit, 1)
            return pages.get(offset, {"count": 10, "items": []})

        items, total_count = await collect_fairness_case_items(
            fetch_page=fetch_page,
            scan_limit=3,
            page_limit=2,
        )
        self.assertEqual(total_count, 10)
        self.assertEqual(len(items), 3)
        self.assertEqual([row["caseId"] for row in items], [1, 2, 3])

    async def test_collect_should_filter_invalid_items(self) -> None:
        async def fetch_page(offset: int, limit: int) -> dict:
            if offset > 0:
                return {"count": "bad", "items": []}
            return {
                "count": "bad",
                "items": [{"caseId": 10}, "skip", None, {"caseId": 11}],
            }

        items, total_count = await collect_fairness_case_items(
            fetch_page=fetch_page,
            scan_limit=20,
            page_limit=5,
        )
        self.assertEqual(total_count, 0)
        self.assertEqual(items, [{"caseId": 10}, {"caseId": 11}])


if __name__ == "__main__":
    unittest.main()
