"""FastAPI web server for Xianyu search tool."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from playwright.async_api import async_playwright

from scraper.ai_analyzer import analyze_items, load_config, save_config
from scraper.auth import check_session_valid, load_context, login_and_save, session_exists
from scraper.exporter import ALL_FIELDS, export
from scraper.parser import parse_items
from scraper.search import search_keyword

app = FastAPI()

# In-memory store: job_id -> file path
export_store: dict[str, Path] = {}
# Prevent concurrent browser sessions
_browser_lock = asyncio.Lock()

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status():
    if not session_exists():
        return {"session": False}
    async with async_playwright() as pw:
        ctx = await load_context(pw)
        valid = await check_session_valid(ctx)
        await ctx.close()
    return {"session": valid}


@app.get("/api/login")
async def login_sse():
    async def _stream():
        def ev(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        if _browser_lock.locked():
            yield ev({"type": "error", "msg": "当前有搜索任务正在运行，请等待完成后再切换账号。"})
            return

        yield ev({"type": "status", "msg": "正在打开浏览器，请在弹出的窗口中登录闲鱼..."})
        try:
            await login_and_save()
            yield ev({"type": "done", "msg": "登录成功，会话已保存！"})
        except Exception as exc:
            yield ev({"type": "error", "msg": str(exc)})

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_search(
    keyword: str,
    pages: int,
    fields: Optional[list[str]],
    delay_min: float,
    delay_max: float,
    locations: Optional[list[str]],
    progress_queue: asyncio.Queue,
) -> dict:
    """Run the actual search in a plain async function (no yield).
    Returns a result dict with keys: error, items, csv_path, excel_path.
    Sends (page_num, total) tuples into progress_queue as pages complete.
    """
    async with _browser_lock:
        async with async_playwright() as pw:
            ctx = await load_context(pw)

            valid = await check_session_valid(ctx)
            if not valid:
                await ctx.close()
                return {"error": "会话已过期，请重新登录。"}

            await progress_queue.put(("status", f"开始搜索「{keyword}」共 {pages} 页..."))

            page_events: asyncio.Queue = asyncio.Queue()

            async def on_page_done(page_num: int, total: int):
                await page_events.put((page_num, total))
                await progress_queue.put(("progress", page_num, total))

            raw_responses = await search_keyword(
                ctx,
                keyword,
                pages=pages,
                delay_min=delay_min,
                delay_max=delay_max,
                on_page_done=on_page_done,
            )
            await ctx.close()

    # Parse outside the lock
    items = parse_items(raw_responses, dedup_keep="latest")

    if locations:
        items = [
            it for it in items
            if any(loc in (it.get("location") or "") for loc in locations)
        ]

    if not items:
        return {"error": None, "items": []}

    field_list = fields if fields else None
    csv_path = export(items, keyword, fmt="csv", fields=field_list)
    excel_path = export(items, keyword, fmt="excel", fields=field_list)

    csv_id = str(uuid.uuid4())
    excel_id = str(uuid.uuid4())
    export_store[csv_id] = csv_path
    export_store[excel_id] = excel_path

    return {
        "error": None,
        "items": items,
        "csv_id": csv_id,
        "csv_url": f"/api/export/{csv_id}",
        "excel_id": excel_id,
        "excel_url": f"/api/export/{excel_id}",
    }


async def _sse_search(
    keyword: str,
    pages: int,
    fields: Optional[list[str]],
    delay_min: float,
    delay_max: float,
    locations: Optional[list[str]],
) -> AsyncGenerator[str, None]:

    def event(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    yield event({"type": "status", "msg": "检查会话..."})

    if not session_exists():
        yield event({"type": "error", "msg": "未找到会话文件，请先点击「切换账号」登录。"})
        return

    yield event({"type": "status", "msg": "启动浏览器..."})

    progress_queue: asyncio.Queue = asyncio.Queue()

    # Launch search as a background task so we can stream progress while it runs
    search_task = asyncio.create_task(
        _run_search(keyword, pages, fields, delay_min, delay_max, locations, progress_queue)
    )

    try:
        while not search_task.done():
            try:
                msg = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if msg[0] == "status":
                yield event({"type": "status", "msg": msg[1]})
            elif msg[0] == "progress":
                yield event({"type": "progress", "page": msg[1], "total": msg[2]})

        # Drain any remaining messages
        while not progress_queue.empty():
            msg = progress_queue.get_nowait()
            if msg[0] == "progress":
                yield event({"type": "progress", "page": msg[1], "total": msg[2]})

        result = search_task.result()

    except Exception as exc:
        yield event({"type": "error", "msg": str(exc)})
        return

    if result.get("error"):
        yield event({"type": "error", "msg": result["error"]})
        return

    items = result.get("items", [])
    yield event({"type": "items", "count": len(items), "data": items})

    # Store items and keyword for analysis
    global _latest_items, _latest_keyword
    _latest_items = items
    _latest_keyword = keyword

    if not items:
        yield event({"type": "done"})
        return

    yield event({
        "type": "export",
        "csv_url": result["csv_url"],
        "excel_url": result["excel_url"],
    })
    yield event({"type": "done"})


@app.get("/api/search")
async def search(
    keyword: str = Query(...),
    pages: int = Query(3, ge=1, le=20),
    fields: Optional[str] = Query(None),
    delay_min: float = Query(1.5, ge=0),
    delay_max: float = Query(3.0, ge=0),
    locations: Optional[str] = Query(None),
):
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None
    if field_list:
        field_list = [f for f in field_list if f in ALL_FIELDS]
    location_list = [loc.strip() for loc in locations.split(",") if loc.strip()] if locations else None

    return StreamingResponse(
        _sse_search(
            keyword=keyword,
            pages=pages,
            fields=field_list,
            delay_min=delay_min,
            delay_max=delay_max,
            locations=location_list,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/export/{job_id}")
async def download(job_id: str):
    path = export_store.get(job_id)
    if path is None or not path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文件不存在或已过期")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
    )


# In-memory store for latest search results
_latest_items: list[dict] = []


@app.get("/api/categories")
async def get_categories():
    """Analyze category statistics from latest search results."""
    if not _latest_items:
        return {"categories": []}

    from collections import defaultdict

    # Group by category
    category_data = defaultdict(lambda: {"count": 0, "prices": [], "want_counts": []})

    for item in _latest_items:
        category = item.get("category", "未分类")
        if not category:
            category = "未分类"

        category_data[category]["count"] += 1

        # Collect prices
        price_str = item.get("price", "")
        if price_str:
            try:
                price = float(price_str.replace("¥", "").replace(",", "").strip())
                category_data[category]["prices"].append(price)
            except:
                pass

        # Collect want counts
        want_str = item.get("want_count", "")
        if want_str:
            try:
                want = int(want_str.replace("人想要", "").strip())
                category_data[category]["want_counts"].append(want)
            except:
                pass

    # Calculate statistics
    categories = []
    for cat_name, data in category_data.items():
        avg_price = sum(data["prices"]) / len(data["prices"]) if data["prices"] else 0
        avg_want = sum(data["want_counts"]) / len(data["want_counts"]) if data["want_counts"] else 0

        # Determine trend based on want count
        if avg_want > 50:
            trend = "hot"
        elif avg_want > 20:
            trend = "rising"
        else:
            trend = "stable"

        categories.append({
            "name": cat_name,
            "count": data["count"],
            "avg_price": round(avg_price, 2),
            "avg_want": round(avg_want, 1),
            "trend": trend
        })

    # Sort by count descending
    categories.sort(key=lambda x: x["count"], reverse=True)

    return {"categories": categories}


@app.get("/api/config")
async def get_config():
    """Get AI configuration (without exposing full API key)."""
    config = load_config()
    ai_config = config.get("ai", {})

    # Mask API key for security
    api_key = ai_config.get("api_key", "")
    masked_key = ""
    if api_key:
        if len(api_key) > 8:
            masked_key = api_key[:4] + "****" + api_key[-4:]
        else:
            masked_key = "****"

    return {
        "provider": ai_config.get("provider", "openai"),
        "api_key": masked_key,
        "api_key_set": bool(api_key),
        "base_url": ai_config.get("base_url", "https://api.openai.com/v1"),
        "model": ai_config.get("model", "gpt-4o-mini"),
        "temperature": ai_config.get("temperature", 0.7)
    }


@app.post("/api/config")
async def update_config(config_update: dict):
    """Update AI configuration."""
    config = load_config()

    if "ai" not in config:
        config["ai"] = {}

    # Update only provided fields
    if "provider" in config_update:
        config["ai"]["provider"] = config_update["provider"]
    if "api_key" in config_update:
        config["ai"]["api_key"] = config_update["api_key"]
    if "base_url" in config_update:
        config["ai"]["base_url"] = config_update["base_url"]
    if "model" in config_update:
        config["ai"]["model"] = config_update["model"]
    if "temperature" in config_update:
        config["ai"]["temperature"] = float(config_update["temperature"])

    save_config(config)
    return {"success": True, "message": "配置已保存"}


@app.get("/api/analyze")
async def analyze():
    """Analyze latest search results using AI."""
    if not _latest_items:
        return {"error": "没有搜索结果可供分析，请先执行搜索", "recommendations": []}

    keyword = _latest_keyword if _latest_keyword else "未知商品"

    result = await analyze_items(_latest_items, keyword)
    return result


# Store keyword with items
_latest_keyword: str = ""
