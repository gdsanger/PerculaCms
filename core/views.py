import logging

from django.shortcuts import get_object_or_404, render
from django.views import View

from .models import Category, NavigationItem, SiteSettings

logger = logging.getLogger(__name__)


class HomeView(View):
    template_name = 'core/home.html'

    def get(self, request):
        logger.debug('HomeView accessed by %s', request.META.get('REMOTE_ADDR'))
        settings = SiteSettings.get_settings()
        nav_items = NavigationItem.objects.filter(
            position='header', is_active=True, parent__isnull=True
        )
        context = {
            'site': settings,
            'nav_items': nav_items,
        }
        return render(request, self.template_name, context)


class CategoryDetailView(View):
    template_name = 'core/category_detail.html'

    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug, is_visible=True)
        pages = category.pages.filter(status='published').order_by('order_in_category')
        context = {
            'site': SiteSettings.get_settings(),
            'category': category,
            'pages': pages,
        }
        return render(request, self.template_name, context)
