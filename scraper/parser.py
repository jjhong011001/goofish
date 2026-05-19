"""Parse mtop JSON API responses into flat item dicts."""

from typing import Any, Optional


def parse_items(raw_responses: list[dict[str, Any]], *, dedup_keep: str = "latest") -> list[dict[str, Any]]:
    """Parse a list of raw mtop API responses into flat item records.

    Only processes responses from mtop.taobao.idlemtopsearch.pc.search.
    Actual items live at: data.resultList[n].data.item.main
    """
    results: list[dict[str, Any]] = []

    for raw in raw_responses:
        # Only parse the main search API, skip hotwords/shade APIs
        api = raw.get("api", "")
        if "pc.search" not in api or "shade" in api:
            continue

        result_list = raw.get("data", {}).get("resultList")
        if not result_list:
            continue

        for entry in result_list:
            try:
                main = entry["data"]["item"]["main"]
            except (KeyError, TypeError):
                continue

            record = _parse_single(main)
            if record:
                results.append(record)

    # Deduplicate by item_id; if missing, fallback to fingerprint
    seen: dict[str, dict[str, Any]] = {}
    def _fingerprint(it: dict[str, Any]) -> str:
        title = (it.get("title") or "").strip().lower()
        seller = (it.get("seller_nick") or "").strip().lower()
        date = (it.get("created_time") or "")[:10]
        return f"{title}|{seller}|{date}"

    for it in results:
        key = it.get("item_id") or _fingerprint(it)
        if key not in seen:
            seen[key] = it
            continue
        # Resolve conflict
        if dedup_keep == "lowest_price":
            try:
                p_new = float(it.get("price") or 0)
                p_old = float(seen[key].get("price") or 0)
            except Exception:
                p_new = p_old = 0
            if p_new < p_old:
                seen[key] = it
        else:  # latest by created_time string
            if (it.get("created_time") or "") > (seen[key].get("created_time") or ""):
                seen[key] = it

    return list(seen.values())


def _parse_single(main: dict[str, Any]) -> Optional[dict[str, Any]]:
    args = main.get("clickParam", {}).get("args", {})
    ex = main.get("exContent", {})
    detail = ex.get("detailParams", {})

    item_id = ex.get("itemId") or args.get("id") or detail.get("itemId") or ""
    title = ex.get("title") or detail.get("title") or ""

    if not item_id and not title:
        return None

    # Price
    price_raw = args.get("price") or detail.get("soldPrice") or ""
    try:
        price = float(str(price_raw).replace("￥", "").replace(",", "").strip())
    except (ValueError, TypeError):
        price = None

    # Condition: tagname is slash-separated e.g. "全新/包邮/极好", first part is condition
    tagname = args.get("tagname", "")
    condition = tagname.split("/")[0] if tagname else ""

    seller_nick = ex.get("userNickName") or detail.get("userNick") or ""
    location = ex.get("area") or ""
    images = ex.get("picUrl") or ""

    category = args.get("catId") or ""

    # publishTime is unix ms timestamp string
    publish_ts = args.get("publishTime") or ""
    if publish_ts:
        try:
            from datetime import datetime, timezone
            ts_sec = int(publish_ts) / 1000
            created_time = datetime.fromtimestamp(ts_sec, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except (ValueError, TypeError):
            created_time = publish_ts
    else:
        created_time = ""

    # No soldCount in search results; use wantNum (people who "want" the item)
    want_num = args.get("wantNum") or "0"
    try:
        want_count = int(want_num)
    except (ValueError, TypeError):
        want_count = 0

    return {
        "item_id": str(item_id),
        "title": str(title),
        "price": price,
        "condition": condition,
        "seller_nick": str(seller_nick),
        "location": str(location),
        "images": str(images),
        "category": str(category),
        "created_time": created_time,
        "want_count": want_count,
    }
