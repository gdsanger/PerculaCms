"""CMS Editor Views – admin-only create/edit for Page objects.

Routes (namespace ``cms``):
  GET/POST  /_cms/pages/new/          ?category=<id>  [&parent=<id>]
  GET/POST  /_cms/pages/<pk>/edit/
  POST      /_cms/pages/<pk>/optimize-summary/
  POST      /_cms/pages/<pk>/optimize-content/
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Category, Page
from .services.page_service import cms_sanitize_html, create_page, sanitize_html, update_page
from .services.agents.service import run_agent
from .services.agents.registry import AgentNotFoundError

logger = logging.getLogger(__name__)

_PERM = 'core.manage_content'


def _require_cms_permission(request):
    """Raise PermissionDenied unless the user has cms manage_content or is superuser."""
    if not (request.user.is_superuser or request.user.has_perm(_PERM)):
        raise PermissionDenied


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_form_context(request, category, parent=None, page=None):
    """Return a context dict for the page form template."""
    categories = Category.objects.all().order_by('order')
    parent_pages = Page.objects.filter(
        category=category, parent__isnull=True
    ).exclude(pk=page.pk if page else None)
    return {
        'site': _get_site(),
        'category': category,
        'parent': parent,
        'page': page,
        'categories': categories,
        'parent_pages': parent_pages,
        'status_choices': Page.Status.choices,
    }


def _get_site():
    from .models import SiteSettings
    return SiteSettings.get_settings()


# ---------------------------------------------------------------------------
# Create View
# ---------------------------------------------------------------------------

@login_required
def page_create_view(request):
    """Create a new root page (no parent) or child page (parent given)."""
    _require_cms_permission(request)

    category_id = request.GET.get('category') or request.POST.get('category')
    parent_id = request.GET.get('parent') or request.POST.get('parent')

    category = get_object_or_404(Category, pk=category_id)
    parent = get_object_or_404(Page, pk=parent_id, category=category) if parent_id else None

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        summary = request.POST.get('summary', '').strip()
        status = request.POST.get('status', Page.Status.DRAFT)
        content_html = request.POST.get('content_html', '')

        if not title:
            messages.error(request, 'Titel ist erforderlich.')
            ctx = _build_form_context(request, category, parent)
            ctx.update({'posted': request.POST})
            return render(request, 'cms/editor/page_form.html', ctx)

        try:
            page = create_page(
                category=category,
                title=title,
                slug=slug,
                summary=summary,
                status=status,
                content_html=content_html,
                parent=parent,
            )
        except ValidationError as exc:
            error_items = exc.message_dict.items() if hasattr(exc, 'message_dict') else [('__all__', exc.messages)]
            for field, errs in error_items:
                for err in errs:
                    messages.error(request, f'{field}: {err}')
            ctx = _build_form_context(request, category, parent)
            ctx.update({'posted': request.POST})
            return render(request, 'cms/editor/page_form.html', ctx)

        messages.success(request, f'Seite „{page.title}" wurde erstellt.')
        return redirect(page.get_absolute_url())

    ctx = _build_form_context(request, category, parent)
    return render(request, 'cms/editor/page_form.html', ctx)


# ---------------------------------------------------------------------------
# Edit View
# ---------------------------------------------------------------------------

@login_required
def page_edit_view(request, pk):
    """Edit an existing page."""
    _require_cms_permission(request)

    page = get_object_or_404(Page, pk=pk)
    category = page.category

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        summary = request.POST.get('summary', '').strip()
        status = request.POST.get('status', page.status)
        content_html = request.POST.get('content_html', '')
        parent_id = request.POST.get('parent') or None
        parent = get_object_or_404(Page, pk=parent_id, category=category) if parent_id else None

        if not title:
            messages.error(request, 'Titel ist erforderlich.')
            ctx = _build_form_context(request, category, parent, page)
            ctx.update({'posted': request.POST})
            return render(request, 'cms/editor/page_form.html', ctx)

        try:
            page = update_page(
                page,
                title=title,
                slug=slug,
                summary=summary,
                status=status,
                content_html=content_html,
                parent=parent,
            )
        except ValidationError as exc:
            error_items = exc.message_dict.items() if hasattr(exc, 'message_dict') else [('__all__', exc.messages)]
            for field, errs in error_items:
                for err in errs:
                    messages.error(request, f'{field}: {err}')
            ctx = _build_form_context(request, category, page.parent, page)
            ctx.update({'posted': request.POST})
            return render(request, 'cms/editor/page_form.html', ctx)

        messages.success(request, f'Seite „{page.title}" wurde gespeichert.')
        return redirect(page.get_absolute_url())

    ctx = _build_form_context(request, category, page.parent, page)
    return render(request, 'cms/editor/page_form.html', ctx)


# ---------------------------------------------------------------------------
# Category Description Edit View
# ---------------------------------------------------------------------------

@login_required
def category_description_edit_view(request, pk):
    """Save a sanitised HTML description for a category."""
    _require_cms_permission(request)

    category = get_object_or_404(Category, pk=pk)

    if request.method != 'POST':
        return redirect('core:category-detail', slug=category.slug)

    description = request.POST.get('description', '')
    category.description = cms_sanitize_html(description)
    category.save()
    messages.success(request, f'Beschreibung von „{category.title}" wurde gespeichert.')
    return redirect('core:category-detail', slug=category.slug)


# ---------------------------------------------------------------------------
# AI Agent Optimization Views
# ---------------------------------------------------------------------------

@login_required
def page_optimize_summary_view(request, pk):
    """Optimize page summary using text-optimization-agent."""
    _require_cms_permission(request)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)

    page = get_object_or_404(Page, pk=pk)

    # Get current summary
    current_summary = page.summary or ''
    if not current_summary.strip():
        return JsonResponse({
            'error': 'Zusammenfassung ist leer. Bitte fügen Sie Text hinzu, bevor Sie optimieren.'
        }, status=400)

    try:
        # Run the text-optimization-agent
        result = run_agent(
            'text-optimization-agent',
            task_input=current_summary,
            user=request.user,
            client_ip=request.META.get('REMOTE_ADDR'),
        )

        # Update the page with the optimized summary
        page.summary = result.output_text
        page.save(update_fields=['summary'])

        logger.info(f"Page {page.pk} summary optimized by {request.user.username}")

        return JsonResponse({
            'success': True,
            'optimized_text': result.output_text,
            'message': 'Zusammenfassung wurde erfolgreich optimiert.'
        })

    except AgentNotFoundError as e:
        logger.error(f"Agent not found: {e}")
        return JsonResponse({
            'error': 'Optimierungs-Agent nicht gefunden.'
        }, status=500)

    except Exception as e:
        logger.error(f"Failed to optimize summary for page {page.pk}: {e}")
        return JsonResponse({
            'error': 'Optimierung fehlgeschlagen. Bitte versuchen Sie es später erneut.'
        }, status=500)


@login_required
def page_create_summary_view(request, pk):
    """Create page summary from content_html using summarize-text-agent."""
    _require_cms_permission(request)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)

    page = get_object_or_404(Page, pk=pk)

    # Get current content
    current_content = page.content_html or ''
    if not current_content.strip():
        return JsonResponse({
            'error': 'Inhalt ist leer. Bitte fügen Sie Inhalt hinzu, bevor Sie eine Zusammenfassung erstellen.'
        }, status=400)

    try:
        # Run the summarize-text-agent
        result = run_agent(
            'summarize-text-agent',
            task_input=current_content,
            user=request.user,
            client_ip=request.META.get('REMOTE_ADDR'),
        )

        # Handle empty/whitespace output
        created_summary = result.output_text.strip() if result.output_text else ''

        # Update the page with the created summary (even if empty)
        page.summary = created_summary
        page.save(update_fields=['summary'])

        logger.info(f"Page {page.pk} summary created from content by {request.user.username}")

        return JsonResponse({
            'success': True,
            'created_text': created_summary,
            'message': 'Zusammenfassung wurde erfolgreich aus dem Inhalt erstellt.'
        })

    except AgentNotFoundError as e:
        logger.error(f"Agent not found: {e}")
        return JsonResponse({
            'error': 'Zusammenfassungs-Agent nicht gefunden.'
        }, status=500)

    except Exception as e:
        logger.error(f"Failed to create summary for page {page.pk}: {e}")
        return JsonResponse({
            'error': 'Erstellung fehlgeschlagen. Bitte versuchen Sie es später erneut.'
        }, status=500)


@login_required
def page_optimize_content_view(request, pk):
    """Restructure page content into a Bootstrap layout using content-html-layout-agent."""
    _require_cms_permission(request)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)

    page = get_object_or_404(Page, pk=pk)

    # Get current content
    current_content = page.content_html or ''
    if not current_content.strip():
        return JsonResponse({
            'error': 'Inhalt ist leer. Bitte fügen Sie Text hinzu, bevor Sie optimieren.'
        }, status=400)

    try:
        # Run the content-html-layout-agent
        result = run_agent(
            'content-html-layout-agent',
            task_input=current_content,
            user=request.user,
            client_ip=request.META.get('REMOTE_ADDR'),
        )

        # Normalize output: empty/whitespace → ""
        new_html = result.output_text.strip() if result.output_text else ''

        # Sanitize the optimized content (for security)
        optimized_content = sanitize_html(new_html) if new_html else ''

        # Update the page with the optimized content
        page.content_html = optimized_content
        page.save(update_fields=['content_html'])

        logger.info(f"Page {page.pk} content restructured to Bootstrap layout by {request.user.username}")

        return JsonResponse({
            'success': True,
            'optimized_text': optimized_content,
            'message': 'Inhalt wurde erfolgreich in ein Bootstrap-Layout umstrukturiert.'
        })

    except AgentNotFoundError as e:
        logger.error(f"Agent not found: {e}")
        return JsonResponse({
            'error': 'Layout-Agent nicht gefunden.'
        }, status=500)

    except Exception as e:
        logger.error(f"Failed to restructure content for page {page.pk}: {e}")
        return JsonResponse({
            'error': 'Optimierung fehlgeschlagen. Bitte versuchen Sie es später erneut.'
        }, status=500)
