"""Service layer for Page create / update operations.

Handles:
- slug auto-generation from title
- server-side HTML sanitisation via bleach
- parent/category constraint enforcement
"""

import logging
import re

import bleach
from django.utils.text import slugify

from ..models import Category, Page

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed HTML for Quill content
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


def _sanitize_html(html: str) -> str:
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
    parent: 'Page | None' = None,
    order_in_category: int = 0,
) -> Page:
    """Create a new Page, sanitising HTML and auto-generating slug if empty."""
    if not slug:
        slug = _auto_slug(title, category)

    page = Page(
        category=category,
        parent=parent,
        title=title,
        slug=slug,
        summary=summary,
        status=status,
        content_html=_sanitize_html(content_html),
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
    parent: 'Page | None' = None,
) -> Page:
    """Update an existing Page, sanitising HTML and auto-generating slug if empty."""
    if not slug:
        slug = _auto_slug(title, page.category, exclude_pk=page.pk)

    page.title = title
    page.slug = slug
    page.summary = summary
    page.status = status
    page.content_html = _sanitize_html(content_html)
    page.parent = parent
    page.clean()
    page.save()
    logger.info('Page updated: pk=%s slug=%s', page.pk, page.slug)
    return page
