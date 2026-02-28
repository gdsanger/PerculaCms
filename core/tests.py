from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from .models import NavigationItem, SiteSettings, Category, Page, PageBlock


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


# ---------------------------------------------------------------------------
# Category Tests
# ---------------------------------------------------------------------------

class CategoryModelTest(TestCase):
    def _make_category(self, **kwargs):
        defaults = dict(key='services', title='Services', slug='services', order=1)
        defaults.update(kwargs)
        return Category.objects.create(**defaults)

    def test_str_representation(self):
        cat = self._make_category()
        self.assertEqual(str(cat), 'Services')

    def test_default_nav_placement_is_header(self):
        cat = self._make_category()
        self.assertEqual(cat.nav_placement, Category.NavPlacement.HEADER)

    def test_default_is_visible_true(self):
        cat = self._make_category()
        self.assertTrue(cat.is_visible)

    def test_key_and_slug_are_unique(self):
        self._make_category()
        with self.assertRaises(Exception):
            self._make_category()  # duplicate key + slug

    def test_ordering_by_order(self):
        self._make_category(key='b', title='B', slug='b', order=2)
        self._make_category(key='a', title='A', slug='a', order=1)
        keys = list(Category.objects.values_list('key', flat=True))
        self.assertEqual(keys, ['a', 'b'])


# ---------------------------------------------------------------------------
# Page Tests
# ---------------------------------------------------------------------------

class PageModelTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(key='home', title='Home', slug='home', order=0)

    def _make_page(self, **kwargs):
        defaults = dict(category=self.cat, title='Welcome', slug='welcome', order_in_category=0)
        defaults.update(kwargs)
        return Page.objects.create(**defaults)

    def test_str_representation(self):
        page = self._make_page()
        self.assertIn('Welcome', str(page))
        self.assertIn('Home', str(page))

    def test_default_status_is_draft(self):
        page = self._make_page()
        self.assertEqual(page.status, Page.Status.DRAFT)

    def test_slug_unique_within_category(self):
        self._make_page()
        with self.assertRaises(Exception):
            self._make_page()  # same category + slug

    def test_same_slug_different_categories(self):
        cat2 = Category.objects.create(key='about', title='About', slug='about', order=1)
        self._make_page()
        # Same slug in a different category must be allowed
        page2 = Page.objects.create(category=cat2, title='Welcome', slug='welcome', order_in_category=0)
        self.assertIsNotNone(page2.pk)

    def test_get_absolute_url(self):
        page = self._make_page()
        self.assertEqual(page.get_absolute_url(), '/home/welcome')

    def test_publish_sets_status_and_published_at(self):
        page = self._make_page()
        self.assertIsNone(page.published_at)
        page.publish()
        page.refresh_from_db()
        self.assertEqual(page.status, Page.Status.PUBLISHED)
        self.assertIsNotNone(page.published_at)

    def test_publish_does_not_overwrite_existing_published_at(self):
        from django.utils import timezone
        ts = timezone.now()
        page = self._make_page(published_at=ts)
        page.publish()
        page.refresh_from_db()
        self.assertEqual(page.published_at, ts)

    def test_clean_rejects_cross_category_parent(self):
        cat2 = Category.objects.create(key='about', title='About', slug='about', order=1)
        parent = Page.objects.create(category=cat2, title='Parent', slug='parent', order_in_category=0)
        child = Page(category=self.cat, title='Child', slug='child', parent=parent, order_in_category=1)
        with self.assertRaises(ValidationError):
            child.clean()

    def test_clean_allows_same_category_parent(self):
        parent = self._make_page()
        child = Page(category=self.cat, title='Child', slug='child', parent=parent, order_in_category=1)
        # Should not raise
        child.clean()

    def test_ordering_by_order_in_category(self):
        Page.objects.create(category=self.cat, title='B', slug='b', order_in_category=2)
        Page.objects.create(category=self.cat, title='A', slug='a', order_in_category=1)
        slugs = list(self.cat.pages.values_list('slug', flat=True))
        self.assertEqual(slugs, ['a', 'b'])


# ---------------------------------------------------------------------------
# PageBlock Tests
# ---------------------------------------------------------------------------

class PageBlockModelTest(TestCase):
    def setUp(self):
        cat = Category.objects.create(key='home', title='Home', slug='home', order=0)
        self.page = Page.objects.create(category=cat, title='Welcome', slug='welcome', order_in_category=0)

    def _make_block(self, **kwargs):
        defaults = dict(page=self.page, type='hero', data={'heading': 'Hi'}, order=0)
        defaults.update(kwargs)
        return PageBlock.objects.create(**defaults)

    def test_str_representation(self):
        block = self._make_block()
        self.assertIn('hero', str(block))
        self.assertIn('0', str(block))

    def test_default_is_enabled_true(self):
        block = self._make_block()
        self.assertTrue(block.is_enabled)

    def test_unique_order_per_page(self):
        self._make_block()
        with self.assertRaises(Exception):
            self._make_block()  # same page + order

    def test_ordering_by_order(self):
        PageBlock.objects.create(page=self.page, type='cta', data={}, order=2)
        PageBlock.objects.create(page=self.page, type='text', data={}, order=1)
        types = list(self.page.blocks.values_list('type', flat=True))
        self.assertEqual(types, ['text', 'cta'])


