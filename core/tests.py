from django.test import TestCase
from django.urls import reverse

from .models import NavigationItem, SiteSettings


class SiteSettingsModelTest(TestCase):
    def test_singleton_enforced(self):
        """Only one SiteSettings instance can exist at a time."""
        s1 = SiteSettings(site_name='First')
        s1.save()
        s2 = SiteSettings(site_name='Second')
        s2.save()
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.objects.first().site_name, 'Second')

    def test_get_settings_creates_default(self):
        """get_settings() creates a default instance if none exists."""
        self.assertEqual(SiteSettings.objects.count(), 0)
        site = SiteSettings.get_settings()
        self.assertIsNotNone(site)
        self.assertEqual(SiteSettings.objects.count(), 1)


class NavigationItemModelTest(TestCase):
    def test_str_representation(self):
        item = NavigationItem(label='Home', url='/', position='header')
        item.save()
        self.assertIn('Home', str(item))
        self.assertIn('header', str(item))


class HomeViewTest(TestCase):
    def test_home_returns_200(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

    def test_home_uses_correct_template(self):
        response = self.client.get(reverse('core:home'))
        self.assertTemplateUsed(response, 'core/home.html')
        self.assertTemplateUsed(response, 'base.html')

    def test_home_context_contains_site(self):
        response = self.client.get(reverse('core:home'))
        self.assertIn('site', response.context)
        self.assertIn('nav_items', response.context)


class LoginViewTest(TestCase):
    def test_login_page_returns_200(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_login_uses_correct_template(self):
        response = self.client.get(reverse('login'))
        self.assertTemplateUsed(response, 'registration/login.html')

