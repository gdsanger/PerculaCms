"""
Service layer for Page create / update operations.

Handles:
- slug auto-generation from title
- server-side HTML sanitisation via bleach
- robust class filtering via BeautifulSoup (no regex-on-HTML)
- parent/category constraint enforcement
- separate sanitization for source (Quill) and layout (Bootstrap) HTML
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

import bleach
from bs4 import BeautifulSoup

from django.conf import settings
from django.utils.text import slugify

from ..models import Category, Page

logger = logging.getLogger(__name__)


# =============================================================================
# Source HTML (Quill) - allow basic formatting + Quill classes (ql-*)
# =============================================================================

SOURCE_ALLOWED_TAGS = [
    # text
    "p", "br", "strong", "em", "u", "s", "span", "div",
    # links & lists
    "a", "ul", "ol", "li",
    # quotes/code
    "blockquote", "code", "pre",
    # headings (title is separate; no need for h1)
    "h2", "h3", "h4",
    "hr",
]

SOURCE_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    # allow class for Quill formatting hooks (filtered later)
    "p": ["class"],
    "div": ["class"],
    "span": ["class"],
    "h2": ["class"],
    "h3": ["class"],
    "h4": ["class"],
    "ul": ["class"],
    "ol": ["class"],
    "li": ["class"],
    "blockquote": ["class"],
    "pre": ["class"],
    "code": ["class"],
}

# Only allow Quill CSS classes in source (keep this tight)
QUILL_CLASS_PATTERNS = [
    r"^ql-.*$",  # e.g. ql-align-center, ql-size-large
]


# =============================================================================
# Layout HTML (AI Bootstrap) - allow structural tags + Bootstrap classes
# =============================================================================

LAYOUT_ALLOWED_TAGS = [
    "div", "section",
    "h2", "h3", "h4", "h5",
    "p", "span", "small",
    "ul", "ol", "li",
    "table", "thead", "tbody", "tr", "td", "th",
    "a", "strong", "em", "blockquote", "hr", "br",
    "i",  # Bootstrap Icons
]

# allow class on many tags; filter classes later via allowlist
LAYOUT_ALLOWED_ATTRIBUTES = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel", "class"],
}

# Tight-ish Bootstrap class allowlist (regex patterns).
# Keep it permissive enough to not nuke valid layouts, but not "anything goes".
BOOTSTRAP_CLASS_PATTERNS = [
    # containers / layout
    r"^container(-fluid)?$",
    r"^row$",
    r"^col$",
    r"^col-(sm|md|lg|xl|xxl)$",
    r"^col-(sm|md|lg|xl|xxl)-([1-9]|1[0-2])$",
    r"^col-([1-9]|1[0-2])$",
    r"^offset-(sm|md|lg|xl|xxl)-([0-9]|1[0-1])$",
    r"^offset-([0-9]|1[0-1])$",
    r"^g-([0-5])$",
    r"^gx-([0-5])$",
    r"^gy-([0-5])$",

    # spacing (0..5)
    r"^m([trblsxe y])?-([0-5])$".replace(" ", ""),  # m-*, mt-*, mx-*, etc.
    r"^p([trblsxe y])?-([0-5])$".replace(" ", ""),

    # cards
    r"^card$",
    r"^card-(body|header|footer|title|subtitle|text)$",

    # alerts, list groups, badges
    r"^alert$",
    r"^alert-(primary|secondary|success|danger|warning|info|light|dark)$",
    r"^list-group$",
    r"^list-group-item$",
    r"^badge$",
    r"^badge-(primary|secondary|success|danger|warning|info|light|dark)$",

    # buttons
    r"^btn$",
    r"^btn-(primary|secondary|success|danger|warning|info|light|dark|link|outline-primary|outline-secondary|outline-success|outline-danger|outline-warning|outline-info|outline-light|outline-dark)$",
    r"^btn-sm$",
    r"^btn-lg$",

    # tables
    r"^table$",
    r"^table-(striped|hover|bordered|borderless|sm|responsive)$",

    # typography
    r"^lead$",
    r"^small$",
    r"^fw-(light|normal|bold|bolder)$",
    r"^text-(start|center|end)$",
    r"^text-(primary|secondary|success|danger|warning|info|light|dark|muted|body|white)$",
    r"^display-[1-6]$",
    r"^fs-[1-6]$",

    # utilities
    r"^d-(none|inline|inline-block|block|grid|flex|inline-flex)$",
    r"^d-(sm|md|lg|xl|xxl)-(none|inline|inline-block|block|grid|flex|inline-flex)$",
    r"^flex-(row|column|row-reverse|column-reverse|wrap|nowrap|fill|grow-0|grow-1|shrink-0|shrink-1)$",
    r"^align-items-(start|center|end|baseline|stretch)$",
    r"^justify-content-(start|center|end|between|around|evenly)$",
    r"^gap-([0-5])$",

    r"^border$",
    r"^border-(0|top|bottom|start|end)$",
    r"^rounded$",
    r"^rounded-(0|1|2|3|4|5|pill|circle)$",
    r"^shadow$",
    r"^shadow-(sm|lg|none)$",
    r"^bg-(primary|secondary|success|danger|warning|info|light|dark|white|transparent)$",

    # widths/heights in Bootstrap 5
    r"^w-(25|50|75|100|auto)$",
    r"^h-(25|50|75|100|auto)$",

    # Bootstrap Icons
    r"^bi$",
    r"^bi-[a-z0-9-]+$",

    # OPTIONAL: your project custom design classes
    # (only keep if you truly use them; otherwise remove)
    r"^percula-(hero|card|icon-box|navbar|logo-icon|stats|cta|footer)$",
    r"^icon-(primary|success|warning|info|purple|rose)$",
    r"^section-badge$",
    r"^badge-pill$",
    r"^gradient-text$",
    r"^testimonial-card$",
]


def _matches_any(patterns: Iterable[str], value: str) -> bool:
    return any(re.match(p, value) for p in patterns)


def _filter_class_list(class_list: list[str], patterns: list[str]) -> list[str]:
    return [c for c in class_list if _matches_any(patterns, c)]


def _ensure_rel_noopener(tag) -> None:
    """Ensure target=_blank links have rel=noopener noreferrer."""
    if tag.name != "a":
        return
    target = tag.get("target")
    if target == "_blank":
        rel = tag.get("rel") or []
        if isinstance(rel, str):
            rel = rel.split()
        rel_set = set(rel)
        rel_set.update(["noopener", "noreferrer"])
        tag["rel"] = sorted(rel_set)


def _filter_classes_in_soup(soup: BeautifulSoup, *, patterns: list[str]) -> None:
    """In-place filter class attributes on all elements."""
    for el in soup.find_all(True):
        classes = el.get("class")
        if not classes:
            continue
        # BeautifulSoup normalizes class into list
        if isinstance(classes, str):
            classes = classes.split()
        filtered = _filter_class_list(list(classes), patterns)
        if filtered:
            el["class"] = filtered
        else:
            del el["class"]


def _strip_disallowed_tags(html: str, *, tags: list[str], attributes: dict) -> str:
    """Bleach clean pass to remove unwanted tags/attrs."""
    return bleach.clean(
        html or "",
        tags=tags,
        attributes=attributes,
        strip=True,
    )


def sanitize_source_html(html: str) -> str:
    """Sanitise Quill-generated HTML.

    - Keep basic formatting tags.
    - Allow Quill CSS hooks (ql-*) but nothing else.
    - Force rel=noopener noreferrer for target=_blank links.
    """
    if not html:
        return ""

    clean = _strip_disallowed_tags(html, tags=SOURCE_ALLOWED_TAGS, attributes=SOURCE_ALLOWED_ATTRIBUTES)

    soup = BeautifulSoup(clean, "html.parser")

    # Filter source classes: only allow ql-*
    _filter_classes_in_soup(soup, patterns=QUILL_CLASS_PATTERNS)

    # Fix rel on external blank targets
    for a in soup.find_all("a"):
        _ensure_rel_noopener(a)

    return str(soup)


def sanitize_layout_html(html: str) -> str:
    """Sanitise AI-generated Bootstrap layout HTML.

    - Remove disallowed tags/attrs via bleach.
    - Filter class attributes to Bootstrap allowlist patterns.
    - Force rel=noopener noreferrer for target=_blank links.
    """
    if not html:
        return ""

    clean = _strip_disallowed_tags(html, tags=LAYOUT_ALLOWED_TAGS, attributes=LAYOUT_ALLOWED_ATTRIBUTES)

    soup = BeautifulSoup(clean, "html.parser")

    # Filter layout classes against Bootstrap allowlist
    _filter_classes_in_soup(soup, patterns=BOOTSTRAP_CLASS_PATTERNS)

    # Fix rel on external blank targets
    for a in soup.find_all("a"):
        _ensure_rel_noopener(a)

    return str(soup)


def cms_sanitize_source_html(html: str) -> str:
    """Feature-flag wrapper for source sanitization."""
    if getattr(settings, "CMS_DISABLE_HTML_SANITIZATION", False):
        logger.warning(
            "CMS HTML sanitization skipped (CMS_DISABLE_HTML_SANITIZATION=true) "
            "- UNSAFE: raw HTML persisted"
        )
        return html or ""
    return sanitize_source_html(html)


def cms_sanitize_layout_html(html: str) -> str:
    """Feature-flag wrapper for layout sanitization."""
    if getattr(settings, "CMS_DISABLE_HTML_SANITIZATION", False):
        logger.warning(
            "CMS HTML sanitization skipped (CMS_DISABLE_HTML_SANITIZATION=true) "
            "- UNSAFE: raw HTML persisted"
        )
        return html or ""
    return sanitize_layout_html(html)


def _auto_slug(title: str, category: Category, exclude_pk: Optional[int] = None) -> str:
    """Generate a unique slug from *title* within *category*."""
    base = slugify(title) or "page"
    slug = base
    n = 1

    qs = Page.objects.filter(category=category, slug=slug)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    while qs.exists():
        slug = f"{base}-{n}"
        n += 1
        qs = Page.objects.filter(category=category, slug=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

    return slug


# =============================================================================
# Public service APIs
# =============================================================================

def create_page(
    *,
    category: Category,
    title: str,
    slug: str = "",
    summary: str = "",
    status: str = Page.Status.DRAFT,
    content_html_source: str = "",
    parent: Optional[Page] = None,
    order_in_category: int = 0,
) -> Page:
    """Create a new Page.

    - Auto slug if empty
    - Sanitise source HTML (Quill)
    - NOTE: layout HTML is generated separately by AI and stored in content_html_layout
    """
    if not slug:
        slug = _auto_slug(title, category)

    page = Page(
        category=category,
        parent=parent,
        title=title,
        slug=slug,
        summary=summary,
        status=status,
        content_html_source=cms_sanitize_source_html(content_html_source),
        order_in_category=order_in_category,
    )
    page.clean()
    page.save()
    logger.info("Page created: pk=%s slug=%s", page.pk, page.slug)
    return page


def update_page(
    page: Page,
    *,
    title: str,
    slug: str = "",
    summary: str = "",
    status: str,
    content_html_source: str = "",
    parent: Optional[Page] = None,
) -> Page:
    """Update a Page (source fields only)."""
    if not slug:
        slug = _auto_slug(title, page.category, exclude_pk=page.pk)

    page.title = title
    page.slug = slug
    page.summary = summary
    page.status = status
    page.parent = parent
    page.content_html_source = cms_sanitize_source_html(content_html_source)

    page.clean()
    page.save(update_fields=["title", "slug", "summary", "status", "parent", "content_html_source"])
    logger.info("Page updated: pk=%s slug=%s", page.pk, page.slug)
    return page


def update_page_layout_html(
    page: Page,
    *,
    content_html_layout: str,
) -> Page:
    """Update only the AI-generated layout HTML."""
    new_html = (content_html_layout or "").strip()
    if not new_html:
        new_html = ""

    page.content_html_layout = cms_sanitize_layout_html(new_html)
    page.save(update_fields=["content_html_layout"])
    logger.info("Page layout updated: pk=%s", page.pk)
    return page