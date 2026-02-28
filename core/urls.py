from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('<slug:category_slug>/<slug:page_slug>/', views.PageDetailView.as_view(), name='page-detail'),
    path('<slug:slug>/', views.CategoryDetailView.as_view(), name='category-detail'),
]
