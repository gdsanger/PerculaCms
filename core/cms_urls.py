from django.urls import path

from . import cms_views

app_name = 'cms'

urlpatterns = [
    path('pages/new/', cms_views.page_create_view, name='page-create'),
    path('pages/<int:pk>/edit/', cms_views.page_edit_view, name='page-edit'),
    path('pages/<int:pk>/optimize-summary/', cms_views.page_optimize_summary_view, name='page-optimize-summary'),
    path('pages/<int:pk>/optimize-content/', cms_views.page_optimize_content_view, name='page-optimize-content'),
    path('categories/<int:pk>/description/', cms_views.category_description_edit_view, name='category-description-edit'),
]
