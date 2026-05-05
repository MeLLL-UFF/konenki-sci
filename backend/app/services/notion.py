import httpx
from typing import Any
from app.config import get_settings

settings = get_settings()

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _rich_text_to_html(rich_texts: list) -> str:
    result = ""
    for rt in rich_texts:
        text = rt.get("plain_text", "")
        if not text:
            continue
        ann = rt.get("annotations", {})
        if ann.get("bold"):
            text = f"<strong>{text}</strong>"
        if ann.get("italic"):
            text = f"<em>{text}</em>"
        if ann.get("code"):
            text = f"<code>{text}</code>"
        href = rt.get("href")
        if href:
            text = f'<a href="{href}" target="_blank" rel="noopener">{text}</a>'
        result += text
    return result


def _blocks_to_html(blocks: list) -> str:
    html = ""
    i = 0
    while i < len(blocks):
        block = blocks[i]
        btype = block.get("type", "")
        content = block.get(btype, {})
        rich = content.get("rich_text", [])
        text = _rich_text_to_html(rich)

        if btype == "paragraph":
            html += f"<p>{text}</p>\n" if text.strip() else "<br>\n"
        elif btype == "heading_1":
            html += f"<h2>{text}</h2>\n"
        elif btype == "heading_2":
            html += f"<h3>{text}</h3>\n"
        elif btype == "heading_3":
            html += f"<h4>{text}</h4>\n"
        elif btype in ("bulleted_list_item", "numbered_list_item"):
            tag = "ul" if btype == "bulleted_list_item" else "ol"
            items = [f"<li>{text}</li>"]
            while i + 1 < len(blocks) and blocks[i + 1].get("type") == btype:
                i += 1
                nb = blocks[i]
                nb_rich = nb.get(btype, {}).get("rich_text", [])
                items.append(f"<li>{_rich_text_to_html(nb_rich)}</li>")
            html += f"<{tag}>{''.join(items)}</{tag}>\n"
        elif btype == "quote":
            html += f"<blockquote>{text}</blockquote>\n"
        elif btype == "callout":
            emoji = content.get("icon", {}).get("emoji", "")
            html += f"<div class='callout'>{emoji} {text}</div>\n"
        elif btype == "divider":
            html += "<hr>\n"
        i += 1
    return html


def _extract_prop(page: dict, name: str) -> Any:
    props = page.get("properties", {})
    prop = props.get(name, {})
    ptype = prop.get("type", "")
    if ptype == "title":
        items = prop.get("title", [])
        return "".join(rt.get("plain_text", "") for rt in items)
    if ptype == "rich_text":
        items = prop.get("rich_text", [])
        return "".join(rt.get("plain_text", "") for rt in items)
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "date":
        d = prop.get("date")
        return d.get("start", "") if d else ""
    return ""


async def list_published() -> list[dict]:
    if not settings.notion_api_key or not settings.notion_database_id:
        return []

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{BASE_URL}/databases/{settings.notion_database_id}/query",
            headers=_headers(),
            json={
                "filter": {"property": "Status", "select": {"equals": "Published"}},
                "sorts": [{"property": "Date", "direction": "descending"}],
            },
        )
        r.raise_for_status()
        results = r.json().get("results", [])

    posts = []
    for page in results:
        slug = _extract_prop(page, "Slug") or page["id"]
        posts.append({
            "id":      page["id"],
            "slug":    slug,
            "title":   _extract_prop(page, "Title"),
            "excerpt": _extract_prop(page, "Excerpt"),
            "date":    _extract_prop(page, "Date"),
        })
    return posts


async def get_post(slug: str) -> dict | None:
    posts = await list_published()
    match = next((p for p in posts if p["slug"] == slug), None)
    if not match:
        return None

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{BASE_URL}/blocks/{match['id']}/children",
            headers=_headers(),
            params={"page_size": 100},
        )
        r.raise_for_status()
        blocks = r.json().get("results", [])

    return {**match, "html": _blocks_to_html(blocks)}
