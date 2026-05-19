"""Search Xianyu via network interception of mtop API responses."""

import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from typing import Any, Optional
from urllib.parse import quote

from playwright.async_api import BrowserContext


SEARCH_URL = "https://www.goofish.com/search?q={query}&page={page}"

# All available fields
ALL_FIELDS = [
    "item_id", "title", "price", "condition",
    "seller_nick", "location", "category",
    "want_count", "created_time", "images",
]


async def search_keyword(
    context: BrowserContext,
    keyword: str,
    pages: int = 3,
    debug: bool = False,
    delay_min: float = 1.5,
    delay_max: float = 3.0,
    on_page_done: Optional[Callable[[int, int], Awaitable[None]]] = None,
) -> list[dict[str, Any]]:
    """Search for keyword across multiple pages, return list of raw API response dicts.

    Args:
        delay_min: Minimum seconds to wait between pages.
        delay_max: Maximum seconds to wait between pages.
        on_page_done: Optional async callback called after each page with (page_num, total_pages).
    """
    all_responses: list[dict[str, Any]] = []
    page = await context.new_page()

    for page_num in range(1, pages + 1):
        url = SEARCH_URL.format(query=quote(keyword), page=page_num)
        captured: list[dict[str, Any]] = []

        async def handle_response(response, _pn=page_num):
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = await response.json()
                if not isinstance(body, dict):
                    return
                body["_url"] = response.url  # stash URL for diagnosis
                if debug:
                    print(f"\n--- Page {_pn} {response.url} ---")
                    print(json.dumps(body, ensure_ascii=False, indent=2))
                captured.append(body)
            except Exception as e:
                if debug:
                    print(f"Failed to parse response: {e}")

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            pass

        await asyncio.sleep(2)
        page.remove_listener("response", handle_response)
        all_responses.extend(captured)

        if on_page_done:
            await on_page_done(page_num, pages)

        if page_num < pages:
            delay = random.uniform(delay_min, delay_max)
            await asyncio.sleep(delay)

    await page.close()
    return all_responses
