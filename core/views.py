import logging

from django.shortcuts import render
from django.views import View

from .models import NavigationItem, SiteSettings

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
