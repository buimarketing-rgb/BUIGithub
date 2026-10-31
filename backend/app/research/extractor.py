"""Extracts structured product information from HTML. Scripts/styles are discarded and nothing
from the page is ever executed."""
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

SECTION_KEYWORDS = {
    "feature": ("feature", "highlight", "benefit", "advantage", "key points"),
    "warranty": ("warranty", "guarantee"),
    "installation": ("install", "installation", "setup", "set up", "mounting"),
    "faq": ("faq", "frequently asked", "questions"),
    "specification": ("specification", "specs", "technical data", "technical details", "dimensions"),
}


@dataclass
class ExtractedItem:
    category: str  # specification | feature | warranty | installation | description | faq | other
    key: str | None
    value: str
    confidence: float


@dataclass
class ExtractedPage:
    title: str
    description: str | None
    text: str
    items: list[ExtractedItem]


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def extract_page(html: str, max_text: int = 20000) -> ExtractedPage:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "form", "nav", "footer", "header"]):
        tag.decompose()
    title = _clean(soup.title.get_text()) if soup.title else ""
    h1 = soup.find("h1")
    if h1 and _clean(h1.get_text()):
        title = _clean(h1.get_text())
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    description = _clean(meta.get("content", "")) if meta else None

    items: list[ExtractedItem] = []
    seen: set[tuple] = set()

    def add(cat: str, key: str | None, value: str, conf: float) -> None:
        value = _clean(value)
        key = _clean(key) if key else None
        if not value or len(value) > 600 or (key and len(key) > 120):
            return
        sig = (cat, (key or "").lower(), value.lower())
        if sig in seen:
            return
        seen.add(sig)
        items.append(ExtractedItem(cat, key, value, conf))

    # 1. Key/value tables -> specifications
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) == 2:
                k, v = _clean(cells[0].get_text(" ")), _clean(cells[1].get_text(" "))
                if k and v and len(k) < 80:
                    add("specification", k.rstrip(":"), v, 0.8)
    # 2. Definition lists
    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                add("specification", dt.get_text(" ").rstrip(":"), dd.get_text(" "), 0.75)
    # 3. Sections by heading keywords
    for heading in soup.find_all(["h2", "h3", "h4"]):
        htext = _clean(heading.get_text()).lower()
        cat = next((c for c, kws in SECTION_KEYWORDS.items() if any(k in htext for k in kws)), None)
        if not cat:
            continue
        for sib in heading.find_next_siblings():
            if sib.name in ("h1", "h2", "h3", "h4"):
                break
            if sib.name in ("ul", "ol"):
                for li in sib.find_all("li"):
                    text = _clean(li.get_text(" "))
                    if cat == "specification" and ":" in text:
                        k, v = text.split(":", 1)
                        add("specification", k, v, 0.7)
                    else:
                        add(cat, None, text, 0.65)
            elif sib.name == "p":
                add(cat, None, sib.get_text(" "), 0.6)
    # 4. "Label: value" lines inside spec-like list items anywhere
    for li in soup.find_all("li"):
        text = _clean(li.get_text(" "))
        m = re.match(r"^([A-Za-z][A-Za-z0-9 ()/\-]{1,40}):\s*(.{1,120})$", text)
        if m and re.search(r"\d", m.group(2)):
            add("specification", m.group(1), m.group(2), 0.55)
    if description:
        add("description", None, description, 0.6)

    text = _clean(soup.get_text(" "))[:max_text]
    return ExtractedPage(title=title or "Untitled page", description=description, text=text, items=items)


def normalize_key(key: str | None) -> str:
    k = re.sub(r"[^a-z0-9 ]", " ", (key or "").lower())
    k = re.sub(r"\b(the|of|max|maximum|rated|approx)\b", " ", k)
    return re.sub(r"\s+", " ", k).strip()


def normalize_value(value: str) -> str:
    v = (value or "").lower().replace(",", "")
    v = re.sub(r"\s+", "", v)
    return v
