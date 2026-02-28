from django.urls import path

from . import cms_views

app_name = 'cms'

urlpatterns = [
    path('pages/new/', cms_views.page_create_view, name='page-create'),
    path('pages/<int:pk>/edit/', cms_views.page_edit_view, name='page-edit'),
]
