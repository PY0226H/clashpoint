from __future__ import annotations

from typing import Any, Awaitable, Callable

FairnessPageFetcher = Callable[[int, int], Awaitable[dict[str, Any]]]


def _normalize_page_items(page: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = page.get("items") if isinstance(page.get("items"), list) else []
    return [item for item in raw_items if isinstance(item, dict)]


async def collect_fairness_case_items(
    *,
    fetch_page: FairnessPageFetcher,
    scan_limit: int,
    page_limit: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    normalized_scan_limit = max(1, int(scan_limit))
    normalized_page_limit = max(1, int(page_limit))
    collected_items: list[dict[str, Any]] = []
    offset = 0
    total_count: int | None = None

    while len(collected_items) < normalized_scan_limit:
        batch_limit = min(normalized_page_limit, normalized_scan_limit - len(collected_items))
        page = await fetch_page(offset, batch_limit)
        if total_count is None:
            try:
                total_count = int(page.get("count") or 0)
            except (TypeError, ValueError):
                total_count = 0
        page_items = _normalize_page_items(page)[:batch_limit]
        if not page_items:
            break
        collected_items.extend(page_items)
        if len(page_items) < batch_limit:
            break
        offset += batch_limit

    return collected_items, int(total_count or 0)
