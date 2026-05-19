"""AI-powered analysis for Xianyu items."""

import json
from pathlib import Path
from typing import Any

import httpx


CONFIG_FILE = Path(__file__).parent.parent / "config.json"


def load_config() -> dict[str, Any]:
    """Load AI configuration from config.json."""
    if not CONFIG_FILE.exists():
        return {
            "ai": {
                "provider": "openai",
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "temperature": 0.7,
            }
        }
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict[str, Any]) -> None:
    """Save AI configuration to config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


async def analyze_items(items: list[dict], keyword: str) -> dict[str, Any]:
    """
    Analyze search results using AI to identify profitable items.

    Args:
        items: List of item dictionaries from search results
        keyword: The search keyword used

    Returns:
        Dictionary with analysis results including recommended items
    """
    config = load_config()
    ai_config = config.get("ai", {})

    api_key = ai_config.get("api_key", "")
    if not api_key:
        # Fallback: lightweight heuristic ranking focusing on value/arb
        try:
            prices = [float(x.get("price", 0)) for x in items[:20] if str(x.get("price", "")).strip()]
            if not prices:
                raise ValueError("no price")
            avg = sum(prices) / len(prices)
            med = sorted(prices)[len(prices)//2]
            p20 = sorted(prices)[max(0, int(len(prices)*0.2)-1)]
        except Exception:
            avg = med = p20 = None

        scored = []
        for idx, it in enumerate(items[:20], 1):
            try:
                price = float(it.get("price", 0) or 0)
            except Exception:
                price = 0.0
            want = int(it.get("want_count", 0) or 0)
            title = (it.get("title") or "").lower()

            risk_words = ["暗病", "有毛病", "不开机", "进水", "仅主板", "id锁", "黑解", "标价错", "寄修"]
            good_words = ["原封", "全套", "带票", "保修", "95新", "99新"]

            value_score = 0
            if avg:
                if price <= 0.85 * avg:
                    value_score += 24
                elif price <= 0.95 * avg:
                    value_score += 14
            if p20 and price <= p20:
                value_score += 10
            if any(w in title for w in good_words):
                value_score += 6
            value_score = min(40, max(0, value_score))

            arbitrage = 0
            if avg:
                gap = avg - price
                if gap > 0:
                    arbitrage += min(20, gap / (avg + 1e-9) * 30)  # scale to 0-30
            if want >= 10:
                arbitrage += 6
            elif want >= 5:
                arbitrage += 3
            arbitrage = min(30, max(0, int(arbitrage)))

            risk = 20
            if any(w in title for w in risk_words):
                risk -= 12
            if price and price < (avg or price) * 0.6:
                risk -= 4
            risk = max(0, min(20, risk))

            cost = 6
            if (it.get("location") or "").strip():
                cost += 2
            cost = min(10, cost)

            score = int(value_score + arbitrage + risk + cost)
            est_market = avg if avg else None
            est_profit = round((est_market - price), 2) if est_market else None

            scored.append({
                "item_id": it.get("item_id", ""),
                "index": idx,
                "score": score,
                "value_score": value_score,
                "arbitrage_score": arbitrage,
                "risk_score": risk,
                "cost_score": cost,
                "est_market_price": est_market,
                "est_profit": est_profit,
                "reason": "基于启发式：低于均价且热度不错，性价比更高",
                "risks": "标题含风险词将被降分"
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "summary": "启发式快速分析：按均价/热度/风险词进行打分排序。",
            "method": "无AI-Key时的本地评分：均价基准+热度+风险词过滤",
            "benchmarks": {"avg_price": avg, "median_price": med, "p20_price": p20},
            "recommendations": scored[:5]
        }

    provider = ai_config.get("provider", "openai")
    base_url = ai_config.get("base_url", "https://api.openai.com/v1")
    model = ai_config.get("model", "gpt-4o-mini")
    temperature = ai_config.get("temperature", 0.7)

    # Normalize base_url
    base_url = base_url.rstrip('/')

    # Prepare item data for AI analysis (limit to top 20 items to avoid token limits)
    items_for_analysis = items[:20]
    items_summary = []

    for idx, item in enumerate(items_for_analysis, 1):
        items_summary.append({
            "index": idx,
            "item_id": item.get("item_id", ""),
            "title": item.get("title", ""),
            "price": item.get("price", ""),
            "condition": item.get("condition", ""),
            "location": item.get("location", ""),
            "want_count": item.get("want_count", ""),
            "seller_nick": item.get("seller_nick", ""),
        })

    # Construct prompt for AI (value-for-money + arbitrage focused)
    prompt = f"""你是资深的二手交易和套利分析师，目标是从闲鱼搜索结果（关键词：{keyword}）中找出“高性价比/可薅羊毛/可赚差价”的标的。

请基于以下量化维度打分并排序（总分100）：
1) 性价比(0-40)：价格相对同类是否偏低；标题/成色信息是否支撑该价格；是否包含配件/保修等隐性价值。
2) 套利潜力(0-30)：是否存在跨平台价差（以常见平台均价为参考的“估计市场价”推断）；是否易于快速转手；需求面（想要数/热门关键词）是否强。
3) 风险控制(0-20)：标题疑点词（“寄修/无维修记录/有暗病/进水/ID锁/无发票/无法当面验机”等）；极端低价是否异常；卖家昵称是否像商家或可疑。
4) 交易成本(0-10)：同城面交优先；异地邮费/耗时；成色磨损可能导致售后纠纷。

启发式参考（无需死板套用）：
- 对同关键词列表，价格处于P20分位以下且想要数≥中位数的，性价比加分；
- 标题中包含“官方保修/原封/全套/带票/95新+”的，加分；包含“问题机/不开机/暗病/ID锁/仅主板”等，风险大幅减分；
- 价格比样本均价低≥15%，且非问题机，套利潜力加分；
- 卖家像C端个体且同城，交易成本更低；

输入样本（最多20条）：
{json.dumps(items_summary, ensure_ascii=False, indent=2)}

请只返回JSON，字段结构如下（严格按键名输出）：
{{
  "summary": "对当前市场价位/供需与主要机会点的2-3句结论",
  "method": "你如何打分与拣选的简述(1-2句)",
  "benchmarks": {{
    "avg_price": 数值或null,
    "median_price": 数值或null,
    "p20_price": 数值或null
  }},
  "recommendations": [
    {{
      "item_id": "商品ID",
      "index": 序号(与输入相同),
      "score": 0-100,
      "value_score": 0-40,
      "arbitrage_score": 0-30,
      "risk_score": 0-20,  
      "cost_score": 0-10,
      "est_market_price": 估计市场价或null,
      "est_profit": 估计可套利利润(市场价-标价)或null,
      "reason": "精炼推荐理由，突出性价比/套利逻辑(<=60字)",
      "risks": "主要风险点，若无可空字符串"
    }}
  ]
}}

要求：
- 至少返回3条，最多5条；
- 不得输出任何JSON以外的文字；
- 严格保证JSON可被解析。"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Handle different API formats
            if provider == "gemini" or "generativelanguage.googleapis.com" in base_url:
                # Gemini API format
                url = f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"

                # Combine system and user messages for Gemini
                full_prompt = f"你是一个专业的二手商品交易分析师，擅长评估商品价值和转售潜力。\n\n{prompt}"

                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{
                            "parts": [{"text": full_prompt}]
                        }],
                        "generationConfig": {
                            "temperature": temperature,
                            "responseMimeType": "application/json"
                        }
                    }
                )
            else:
                # OpenAI-compatible API format
                if not base_url.endswith('/v1'):
                    base_url = base_url + '/v1'

                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一个专业的二手商品交易分析师，擅长评估商品价值和转售潜力。"
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": temperature,
                        "response_format": {"type": "json_object"}
                    }
                )

            if response.status_code != 200:
                return {
                    "error": f"AI API 调用失败: {response.status_code} {response.text}",
                    "recommendations": []
                }

            result = response.json()


            # Extract content based on API format
            if provider == "gemini" or "generativelanguage.googleapis.com" in base_url:
                # Gemini response format
                if "candidates" not in result or not result["candidates"]:
                    return {
                        "error": f"Gemini API 返回格式错误: {json.dumps(result, ensure_ascii=False)}",
                        "recommendations": []
                    }
                content = result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                # OpenAI response format
                if "choices" not in result:
                    return {
                        "error": f"API 返回格式错误，缺少 choices 字段: {json.dumps(result, ensure_ascii=False)}",
                        "recommendations": []
                    }

                if not result["choices"] or len(result["choices"]) == 0:
                    return {
                        "error": "API 返回的 choices 为空",
                        "recommendations": []
                    }

                content = result["choices"][0]["message"]["content"]


            if not content or content.strip() == "":
                return {
                    "error": "AI 返回内容为空",
                    "recommendations": []
                }

            # Clean up markdown code blocks if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            elif content.startswith("```"):
                content = content[3:]  # Remove ```

            if content.endswith("```"):
                content = content[:-3]  # Remove trailing ```

            content = content.strip()

            try:
                analysis = json.loads(content)
            except json.JSONDecodeError as je:
                return {
                    "error": f"AI 返回的内容不是有效的 JSON: {content[:200]}...",
                    "recommendations": []
                }

            # Enrich recommendations with full item data
            for rec in analysis.get("recommendations", []):
                idx = rec.get("index", 0)
                if 1 <= idx <= len(items_for_analysis):
                    rec["item"] = items_for_analysis[idx - 1]

            return analysis

    except json.JSONDecodeError as je:
        return {
            "error": f"JSON 解析失败: {str(je)}",
            "recommendations": []
        }
    except KeyError as ke:
        return {
            "error": f"API 响应缺少必要字段: {str(ke)}",
            "recommendations": []
        }
    except Exception as e:
        return {
            "error": f"AI 分析失败: {str(e)}",
            "recommendations": []
        }
