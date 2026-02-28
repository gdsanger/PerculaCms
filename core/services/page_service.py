"""Service layer for Page create / update operations.

Handles:
- slug auto-generation from title
- server-side HTML sanitisation via bleach
- parent/category constraint enforcement
- separate sanitization for source (Quill) and layout (Bootstrap) HTML
"""

import logging
import re

import bleach
from django.conf import settings
from django.utils.text import slugify

from ..models import Category, Page

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed HTML for Quill content (source)
# ---------------------------------------------------------------------------

ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 's',
    'a', 'ul', 'ol', 'li',
    'blockquote', 'code', 'pre',
    'h1', 'h2', 'h3', 'h4',
    'hr',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
}

# ---------------------------------------------------------------------------
# Allowed HTML for Bootstrap Layout (AI-generated)
# ---------------------------------------------------------------------------

LAYOUT_ALLOWED_TAGS = [
    'div', 'section', 'h2', 'h3', 'h4',
    'p', 'ul', 'ol', 'li',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
    'a', 'strong', 'em', 'blockquote', 'hr', 'br',
    'i',  # for Bootstrap icons
]

# Bootstrap class allowlist (regex patterns)
BOOTSTRAP_CLASS_PATTERNS = [
    r'^container(-fluid)?$',
    r'^row$',
    r'^col(-\w+)?(-\d+)?$',
    r'^card(-\w+)?$',
    r'^alert(-\w+)?$',
    r'^list-group(-\w+)?$',
    r'^table(-\w+)?$',
    r'^btn(-\w+)?$',
    r'^text-\w+$',
    r'^fw-\w+$',
    r'^lead$',
    r'^bi(-\w+)?$',  # Bootstrap icons
    r'^d-\w+$',  # display utilities
    r'^flex-\w+$',  # flexbox utilities
    r'^gap-\d+$',
    r'^m[tbsxye]?-\d+$',  # margin utilities
    r'^p[tbsxye]?-\d+$',  # padding utilities
    r'^border(-\w+)?$',
    r'^rounded(-\w+)?$',
    r'^shadow(-\w+)?$',
    r'^bg-\w+$',  # background colors
    r'^w-\d+$',  # width utilities
    r'^h-\d+$',  # height utilities
]


def _is_bootstrap_class_allowed(class_name: str) -> bool:
    """Check if a class name matches Bootstrap allowlist patterns."""
    return any(re.match(pattern, class_name) for pattern in BOOTSTRAP_CLASS_PATTERNS)


def _filter_classes(classes: str) -> str:
    """Filter classes to only include Bootstrap-allowed classes."""
    if not classes:
        return ''
    class_list = classes.split()
    allowed = [c for c in class_list if _is_bootstrap_class_allowed(c)]
    return ' '.join(allowed)


def sanitize_html(html: str) -> str:
    """Sanitise Quill-generated HTML via bleach allowlist.

    Also sets rel="noopener noreferrer" on any link that uses target="_blank".
    """
    if not html:
        return ''

    clean = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )

    # Ensure target="_blank" links carry rel="noopener noreferrer"
    def _fix_link(match):
        tag = match.group(0)
        if 'target="_blank"' in tag or "target='_blank'" in tag:
            if 'noopener' not in tag:
                tag = tag.rstrip('>') + ' rel="noopener noreferrer">'
        return tag

    clean = re.sub(r'<a [^>]+>', _fix_link, clean)
    return clean


def sanitize_layout_html(html: str) -> str:
    """Sanitise AI-generated Bootstrap layout HTML.

    - Allows Bootstrap-specific tags (div, section, card structure, etc.)
    - Filters class attributes to only allow Bootstrap classes
    - Removes scripts, inline styles, SVG, etc.
    """
    if not html:
        return ''

    # First pass: clean with bleach
    clean = bleach.clean(
        html,
        tags=LAYOUT_ALLOWED_TAGS,
        attributes={
            'div': ['class'],
            'section': ['class'],
            'h2': ['class'],
            'h3': ['class'],
            'h4': ['class'],
            'p': ['class'],
            'ul': ['class'],
            'ol': ['class'],
            'li': ['class'],
            'table': ['class'],
            'thead': ['class'],
            'tbody': ['class'],
            'tr': ['class'],
            'td': ['class'],
            'th': ['class'],
            'a': ['href', 'title', 'target', 'rel', 'class'],
            'strong': ['class'],
            'em': ['class'],
            'blockquote': ['class'],
            'i': ['class'],  # for Bootstrap icons
        },
        strip=True,
    )

    # Second pass: filter classes to Bootstrap allowlist
    def _filter_class_attr(match):
        tag_start = match.group(1)
        classes = match.group(2)
        filtered = _filter_classes(classes)
        if filtered:
            return f'{tag_start}class="{filtered}"'
        # Remove empty class attribute
        return tag_start.rstrip()

    clean = re.sub(r'(<[^>]+\s)class="([^"]*)"', _filter_class_attr, clean)

    # Ensure target="_blank" links carry rel="noopener noreferrer"
    def _fix_link(match):
        tag = match.group(0)
        if 'target="_blank"' in tag or "target='_blank'" in tag:
            if 'noopener' not in tag:
                tag = tag.rstrip('>') + ' rel="noopener noreferrer">'
        return tag

    clean = re.sub(r'<a [^>]+>', _fix_link, clean)
    return clean


def cms_sanitize_html(html: str) -> str:
    """CMS-editor save wrapper: sanitize HTML unless the feature flag disables it.

    When ``settings.CMS_DISABLE_HTML_SANITIZATION`` is ``True`` the raw HTML is
    returned unchanged and a warning is logged (debug/test use only).
    """
    if getattr(settings, 'CMS_DISABLE_HTML_SANITIZATION', False):
        logger.warning(
            'CMS HTML sanitization skipped (CMS_DISABLE_HTML_SANITIZATION=true)'
            ' - UNSAFE: raw HTML persisted'
        )
        return html if html else ''
    return sanitize_html(html)


def _auto_slug(title: str, category: Category, exclude_pk=None) -> str:
    """Generate a unique slug from *title* within *category*."""
    base = slugify(title) or 'page'
    slug = base
    n = 1
    qs = Page.objects.filter(category=category, slug=slug)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        slug = f'{base}-{n}'
        n += 1
        qs = Page.objects.filter(category=category, slug=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
    return slug


def create_page(
    *,
    category: Category,
    title: str,
    slug: str = '',
    summary: str = '',
    status: str = Page.Status.DRAFT,
    content_html: str = '',
    content_html_source: str = '',
    parent: 'Page | None' = None,
    order_in_category: int = 0,
) -> Page:
    """Create a new Page, sanitising HTML and auto-generating slug if empty.

    Prefers content_html_source if provided, falls back to content_html for backward compatibility.
    """
    if not slug:
        slug = _auto_slug(title, category)

    # Prefer content_html_source if provided, else use content_html
    source_content = content_html_source if content_html_source else content_html

    page = Page(
        category=category,
        parent=parent,
        title=title,
        slug=slug,
        summary=summary,
        status=status,
        content_html=cms_sanitize_html(content_html),  # Keep for backward compatibility
        content_html_source=cms_sanitize_html(source_content),
        order_in_category=order_in_category,
    )
    page.clean()
    page.save()
    logger.info('Page created: pk=%s slug=%s', page.pk, page.slug)
    return page


def update_page(
    page: Page,
    *,
    title: str,
    slug: str = '',
    summary: str = '',
    status: str,
    content_html: str = '',
    content_html_source: str = '',
    parent: 'Page | None' = None,
) -> Page:
    """Update an existing Page, sanitising HTML and auto-generating slug if empty.

    Prefers content_html_source if provided, falls back to content_html for backward compatibility.
    """
    if not slug:
        slug = _auto_slug(title, page.category, exclude_pk=page.pk)

    # Prefer content_html_source if provided, else use content_html
    source_content = content_html_source if content_html_source else content_html

    page.title = title
    page.slug = slug
    page.summary = summary
    page.status = status
    page.content_html = cms_sanitize_html(content_html)  # Keep for backward compatibility
    page.content_html_source = cms_sanitize_html(source_content)
    page.parent = parent
    page.clean()
    page.save()
    logger.info('Page updated: pk=%s slug=%s', page.pk, page.slug)
    return page
