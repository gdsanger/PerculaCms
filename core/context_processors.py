from .models import Category


def nav_categories(request):
    """Inject header categories into every template context."""
    categories = Category.objects.filter(
        is_visible=True,
        nav_placement=Category.NavPlacement.HEADER,
    ).order_by('order')
    return {'nav_categories': categories}
