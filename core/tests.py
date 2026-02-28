from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from unittest.mock import MagicMock, patch
from decimal import Decimal

from .models import (
    NavigationItem, SiteSettings, Category, Page, PageBlock,
    MediaFolder, MediaAsset, MediaAssetUsage,
    Redirect, PageRevision, Snippet, VisitorSession, BehaviorEvent,
    AIProvider, AIModel, AIJobsHistory,
)


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
# CategoryDetailView Tests
# ---------------------------------------------------------------------------

class CategoryDetailViewTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(
            key='services', title='Services', slug='services',
            order=1, is_visible=True, nav_placement=Category.NavPlacement.HEADER,
        )

    def test_returns_200_for_visible_category(self):
        response = self.client.get(reverse('core:category-detail', args=['services']))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        response = self.client.get(reverse('core:category-detail', args=['services']))
        self.assertTemplateUsed(response, 'core/category_detail.html')
        self.assertTemplateUsed(response, 'base.html')

    def test_context_contains_category_and_pages(self):
        response = self.client.get(reverse('core:category-detail', args=['services']))
        self.assertEqual(response.context['category'], self.cat)
        self.assertIn('pages', response.context)

    def test_returns_404_for_invisible_category(self):
        Category.objects.create(
            key='hidden', title='Hidden', slug='hidden',
            order=2, is_visible=False,
        )
        response = self.client.get(reverse('core:category-detail', args=['hidden']))
        self.assertEqual(response.status_code, 404)

    def test_returns_404_for_unknown_slug(self):
        response = self.client.get(reverse('core:category-detail', args=['does-not-exist']))
        self.assertEqual(response.status_code, 404)

    def test_empty_pages_renders_without_error(self):
        response = self.client.get(reverse('core:category-detail', args=['services']))
        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(response.context['pages'], [])


# ---------------------------------------------------------------------------
# nav_categories Context Processor Tests
# ---------------------------------------------------------------------------

class NavCategoriesContextProcessorTest(TestCase):
    def test_nav_categories_present_on_home(self):
        response = self.client.get(reverse('core:home'))
        self.assertIn('nav_categories', response.context)

    def test_nav_categories_only_header_and_visible(self):
        Category.objects.create(
            key='header-cat', title='Header Cat', slug='header-cat',
            order=1, is_visible=True, nav_placement=Category.NavPlacement.HEADER,
        )
        Category.objects.create(
            key='footer-cat', title='Footer Cat', slug='footer-cat',
            order=2, is_visible=True, nav_placement=Category.NavPlacement.FOOTER,
        )
        Category.objects.create(
            key='hidden-cat', title='Hidden Cat', slug='hidden-cat',
            order=3, is_visible=False, nav_placement=Category.NavPlacement.HEADER,
        )
        response = self.client.get(reverse('core:home'))
        slugs = list(response.context['nav_categories'].values_list('slug', flat=True))
        self.assertIn('header-cat', slugs)
        self.assertNotIn('footer-cat', slugs)
        self.assertNotIn('hidden-cat', slugs)

    def test_nav_categories_sorted_by_order(self):
        Category.objects.create(
            key='z-cat', title='Z Cat', slug='z-cat',
            order=2, is_visible=True, nav_placement=Category.NavPlacement.HEADER,
        )
        Category.objects.create(
            key='a-cat', title='A Cat', slug='a-cat',
            order=1, is_visible=True, nav_placement=Category.NavPlacement.HEADER,
        )
        response = self.client.get(reverse('core:home'))
        slugs = list(response.context['nav_categories'].values_list('slug', flat=True))
        self.assertEqual(slugs, ['a-cat', 'z-cat'])

    def test_empty_nav_categories_renders_without_error(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(list(response.context['nav_categories']), [])




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


# ---------------------------------------------------------------------------
# MediaFolder Tests
# ---------------------------------------------------------------------------

class MediaFolderModelTest(TestCase):
    def _make_folder(self, name='images', parent=None):
        return MediaFolder.objects.create(name=name, parent=parent)

    def test_str_representation(self):
        folder = self._make_folder()
        self.assertEqual(str(folder), 'images')

    def test_unique_name_within_same_parent(self):
        self._make_folder(name='docs')
        duplicate = MediaFolder(name='docs', parent=None)
        with self.assertRaises(ValidationError):
            duplicate.clean()

    def test_same_name_allowed_in_different_parents(self):
        parent1 = self._make_folder(name='parent1')
        parent2 = self._make_folder(name='parent2')
        child1 = MediaFolder.objects.create(name='sub', parent=parent1)
        child2 = MediaFolder.objects.create(name='sub', parent=parent2)
        self.assertNotEqual(child1.pk, child2.pk)

    def test_nested_hierarchy(self):
        root = self._make_folder(name='root')
        child = MediaFolder.objects.create(name='child', parent=root)
        self.assertEqual(child.parent, root)
        self.assertIn(child, root.children.all())

    def test_clean_rejects_cyclic_parent(self):
        root = self._make_folder(name='root')
        child = MediaFolder.objects.create(name='child', parent=root)
        # Make root point to child → cycle
        root.parent = child
        with self.assertRaises(ValidationError):
            root.clean()


# ---------------------------------------------------------------------------
# MediaAsset Tests
# ---------------------------------------------------------------------------

class MediaAssetModelTest(TestCase):
    def _make_asset(self, **kwargs):
        defaults = dict(
            title='Test Image',
            asset_type=MediaAsset.AssetType.IMAGE,
            file='media_assets/test.png',
            original_filename='test.png',
            mime_type='image/png',
            file_size=1024,
        )
        defaults.update(kwargs)
        return MediaAsset.objects.create(**defaults)

    def test_str_representation(self):
        asset = self._make_asset()
        self.assertEqual(str(asset), 'Test Image')

    def test_default_status_is_active(self):
        asset = self._make_asset()
        self.assertEqual(asset.status, MediaAsset.Status.ACTIVE)

    def test_default_asset_type(self):
        asset = self._make_asset()
        self.assertEqual(asset.asset_type, MediaAsset.AssetType.IMAGE)

    def test_asset_in_folder(self):
        folder = MediaFolder.objects.create(name='images')
        asset = self._make_asset(folder=folder)
        self.assertEqual(asset.folder, folder)
        self.assertIn(asset, folder.assets.all())

    def test_image_dimensions(self):
        asset = self._make_asset(width=1920, height=1080)
        self.assertEqual(asset.width, 1920)
        self.assertEqual(asset.height, 1080)

    def test_video_duration(self):
        asset = self._make_asset(
            title='Test Video',
            asset_type=MediaAsset.AssetType.VIDEO,
            file='media_assets/test.mp4',
            original_filename='test.mp4',
            mime_type='video/mp4',
            duration_seconds=120,
        )
        self.assertEqual(asset.duration_seconds, 120)

    def test_document_page_count(self):
        asset = self._make_asset(
            title='Test PDF',
            asset_type=MediaAsset.AssetType.DOCUMENT,
            file='media_assets/test.pdf',
            original_filename='test.pdf',
            mime_type='application/pdf',
            page_count=5,
        )
        self.assertEqual(asset.page_count, 5)

    def test_preview_image_asset(self):
        thumb = self._make_asset(title='Thumbnail')
        pdf = self._make_asset(
            title='Report',
            asset_type=MediaAsset.AssetType.DOCUMENT,
            file='media_assets/report.pdf',
            original_filename='report.pdf',
            mime_type='application/pdf',
            preview_image_asset=thumb,
        )
        self.assertEqual(pdf.preview_image_asset, thumb)
        self.assertIn(pdf, thumb.preview_for.all())

    def test_tags_default_is_empty_list(self):
        asset = self._make_asset()
        self.assertEqual(asset.tags, [])


# ---------------------------------------------------------------------------
# Page.og_image_asset FK Tests
# ---------------------------------------------------------------------------

class PageOgImageAssetTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(key='home', title='Home', slug='home', order=0)

    def test_og_image_asset_nullable(self):
        page = Page.objects.create(
            category=self.cat, title='Welcome', slug='welcome', order_in_category=0
        )
        self.assertIsNone(page.og_image_asset)

    def test_og_image_asset_can_be_set(self):
        asset = MediaAsset.objects.create(
            title='OG Image',
            asset_type=MediaAsset.AssetType.IMAGE,
            file='media_assets/og.png',
            original_filename='og.png',
            mime_type='image/png',
            file_size=2048,
        )
        page = Page.objects.create(
            category=self.cat, title='About', slug='about',
            order_in_category=0, og_image_asset=asset,
        )
        page.refresh_from_db()
        self.assertEqual(page.og_image_asset, asset)
        self.assertIn(page, asset.og_image_pages.all())


# ---------------------------------------------------------------------------
# MediaAssetUsage Tests
# ---------------------------------------------------------------------------

class MediaAssetUsageModelTest(TestCase):
    def setUp(self):
        self.asset = MediaAsset.objects.create(
            title='Hero Image',
            asset_type=MediaAsset.AssetType.IMAGE,
            file='media_assets/hero.png',
            original_filename='hero.png',
            mime_type='image/png',
            file_size=4096,
        )
        cat = Category.objects.create(key='home', title='Home', slug='home', order=0)
        self.page = Page.objects.create(
            category=cat, title='Welcome', slug='welcome', order_in_category=0
        )
        self.block = PageBlock.objects.create(
            page=self.page, type='hero',
            data={'image_asset_id': str(self.asset.pk)}, order=0
        )

    def _block_ct(self):
        return ContentType.objects.get_for_model(PageBlock)

    def test_usage_creation(self):
        usage = MediaAssetUsage.objects.create(
            asset=self.asset,
            content_type=self._block_ct(),
            object_id=self.block.pk,
            field='hero_image',
        )
        self.assertEqual(usage.asset, self.asset)
        self.assertEqual(usage.content_object, self.block)
        self.assertIn(usage, self.asset.usages.all())

    def test_str_representation(self):
        usage = MediaAssetUsage.objects.create(
            asset=self.asset,
            content_type=self._block_ct(),
            object_id=self.block.pk,
            field='hero_image',
        )
        self.assertIn('Hero Image', str(usage))
        self.assertIn('hero_image', str(usage))

    def test_unique_constraint(self):
        ct = self._block_ct()
        MediaAssetUsage.objects.create(
            asset=self.asset, content_type=ct, object_id=self.block.pk, field='hero_image'
        )
        with self.assertRaises(Exception):
            MediaAssetUsage.objects.create(
                asset=self.asset, content_type=ct, object_id=self.block.pk, field='hero_image'
            )

    def test_page_as_usage_target(self):
        page_ct = ContentType.objects.get_for_model(Page)
        usage = MediaAssetUsage.objects.create(
            asset=self.asset,
            content_type=page_ct,
            object_id=self.page.pk,
            field='og_image',
        )
        self.assertEqual(usage.content_object, self.page)



# ---------------------------------------------------------------------------
# Redirect Tests
# ---------------------------------------------------------------------------

class RedirectModelTest(TestCase):
    def _make_redirect(self, **kwargs):
        defaults = dict(from_path='/old', to_path='/new')
        defaults.update(kwargs)
        return Redirect.objects.create(**defaults)

    def test_str_representation(self):
        r = self._make_redirect()
        self.assertIn('/old', str(r))
        self.assertIn('/new', str(r))

    def test_default_status_code_301(self):
        r = self._make_redirect()
        self.assertEqual(r.status_code, 301)

    def test_default_is_active_true(self):
        r = self._make_redirect()
        self.assertTrue(r.is_active)

    def test_default_hit_count_zero(self):
        r = self._make_redirect()
        self.assertEqual(r.hit_count, 0)

    def test_unique_from_path(self):
        self._make_redirect()
        with self.assertRaises(Exception):
            self._make_redirect()

    def test_ordering_by_from_path(self):
        Redirect.objects.create(from_path='/b', to_path='/x')
        Redirect.objects.create(from_path='/a', to_path='/y')
        paths = list(Redirect.objects.values_list('from_path', flat=True))
        self.assertEqual(paths, ['/a', '/b'])

    def test_clean_rejects_identical_paths(self):
        r = Redirect(from_path='/same', to_path='/same')
        with self.assertRaises(ValidationError):
            r.clean()

    def test_clean_allows_different_paths(self):
        r = Redirect(from_path='/old', to_path='/new')
        r.clean()  # should not raise


# ---------------------------------------------------------------------------
# PageRevision Tests
# ---------------------------------------------------------------------------

class PageRevisionModelTest(TestCase):
    def setUp(self):
        cat = Category.objects.create(key='home', title='Home', slug='home', order=0)
        self.page = Page.objects.create(
            category=cat, title='Welcome', slug='welcome', order_in_category=0
        )

    def _make_revision(self, revision_no=1, **kwargs):
        defaults = dict(
            page=self.page,
            revision_no=revision_no,
            snapshot={'page': {'title': 'Welcome'}, 'blocks': []},
        )
        defaults.update(kwargs)
        return PageRevision.objects.create(**defaults)

    def test_str_representation(self):
        rev = self._make_revision()
        self.assertIn('rev 1', str(rev))

    def test_unique_revision_no_per_page(self):
        self._make_revision(revision_no=1)
        with self.assertRaises(Exception):
            self._make_revision(revision_no=1)

    def test_same_revision_no_different_pages(self):
        cat2 = Category.objects.create(key='about', title='About', slug='about', order=1)
        page2 = Page.objects.create(
            category=cat2, title='About', slug='about', order_in_category=0
        )
        self._make_revision(revision_no=1)
        rev2 = PageRevision.objects.create(
            page=page2, revision_no=1,
            snapshot={'page': {}, 'blocks': []},
        )
        self.assertIsNotNone(rev2.pk)

    def test_snapshot_is_json(self):
        rev = self._make_revision(snapshot={'page': {'title': 'T'}, 'blocks': [{'type': 'hero'}]})
        rev.refresh_from_db()
        self.assertEqual(rev.snapshot['blocks'][0]['type'], 'hero')

    def test_note_defaults_blank(self):
        rev = self._make_revision()
        self.assertEqual(rev.note, '')


# ---------------------------------------------------------------------------
# Snippet Tests
# ---------------------------------------------------------------------------

class SnippetModelTest(TestCase):
    def _make_snippet(self, **kwargs):
        defaults = dict(key='footer.primary', title='Primary Footer', type='richtext', data={'html': '<p>Hi</p>'})
        defaults.update(kwargs)
        return Snippet.objects.create(**defaults)

    def test_str_representation(self):
        s = self._make_snippet()
        self.assertEqual(str(s), 'footer.primary')

    def test_unique_key(self):
        self._make_snippet()
        with self.assertRaises(Exception):
            self._make_snippet()

    def test_default_is_active_true(self):
        s = self._make_snippet()
        self.assertTrue(s.is_active)

    def test_tags_default_empty_list(self):
        s = self._make_snippet()
        self.assertEqual(s.tags, [])

    def test_ordering_by_key(self):
        Snippet.objects.create(key='z.key', title='Z', type='richtext')
        Snippet.objects.create(key='a.key', title='A', type='richtext')
        keys = list(Snippet.objects.values_list('key', flat=True))
        self.assertEqual(keys, ['a.key', 'z.key'])


# ---------------------------------------------------------------------------
# VisitorSession Tests
# ---------------------------------------------------------------------------

class VisitorSessionModelTest(TestCase):
    def _make_session(self, **kwargs):
        return VisitorSession.objects.create(**kwargs)

    def test_id_is_uuid(self):
        import uuid
        session = self._make_session()
        self.assertIsInstance(session.id, uuid.UUID)

    def test_str_is_uuid_string(self):
        session = self._make_session()
        self.assertEqual(str(session), str(session.id))

    def test_default_is_bot_suspected_false(self):
        session = self._make_session()
        self.assertFalse(session.is_bot_suspected)

    def test_consent_defaults_empty_dict(self):
        session = self._make_session()
        self.assertEqual(session.consent, {})


# ---------------------------------------------------------------------------
# BehaviorEvent Tests
# ---------------------------------------------------------------------------

class BehaviorEventModelTest(TestCase):
    def setUp(self):
        self.session = VisitorSession.objects.create()

    def _make_event(self, **kwargs):
        defaults = dict(session=self.session, event_type='page_view', payload={'path': '/home'})
        defaults.update(kwargs)
        return BehaviorEvent.objects.create(**defaults)

    def test_str_representation(self):
        event = self._make_event()
        self.assertIn('page_view', str(event))

    def test_event_linked_to_session(self):
        event = self._make_event()
        self.assertIn(event, self.session.events.all())

    def test_payload_defaults_empty_dict(self):
        event = BehaviorEvent.objects.create(session=self.session, event_type='scroll_depth')
        self.assertEqual(event.payload, {})

    def test_ordering_by_occurred_at_desc(self):
        from django.utils import timezone
        import datetime
        t1 = timezone.now() - datetime.timedelta(seconds=10)
        t2 = timezone.now()
        BehaviorEvent.objects.create(session=self.session, event_type='first', occurred_at=t1)
        BehaviorEvent.objects.create(session=self.session, event_type='second', occurred_at=t2)
        types = list(self.session.events.values_list('event_type', flat=True))
        self.assertEqual(types, ['second', 'first'])


# ---------------------------------------------------------------------------
# AIProvider Tests
# ---------------------------------------------------------------------------

class AIProviderModelTest(TestCase):
    def _make_provider(self, **kwargs):
        defaults = dict(
            name='OpenAI Test',
            provider_type=AIProvider.ProviderType.OPENAI,
            api_key='sk-test',
        )
        defaults.update(kwargs)
        return AIProvider.objects.create(**defaults)

    def test_str_representation(self):
        p = self._make_provider()
        self.assertIn('OpenAI Test', str(p))
        self.assertIn('OpenAI', str(p))

    def test_default_is_active_true(self):
        p = self._make_provider()
        self.assertTrue(p.is_active)

    def test_provider_type_choices(self):
        for pt in (AIProvider.ProviderType.OPENAI, AIProvider.ProviderType.GEMINI, AIProvider.ProviderType.CLAUDE):
            p = self._make_provider(name=f'{pt} provider', provider_type=pt)
            self.assertEqual(p.provider_type, pt)


# ---------------------------------------------------------------------------
# AIModel Tests
# ---------------------------------------------------------------------------

class AIModelModelTest(TestCase):
    def setUp(self):
        self.provider = AIProvider.objects.create(
            name='OpenAI Test', provider_type='OpenAI', api_key='sk-test'
        )

    def _make_model(self, **kwargs):
        defaults = dict(
            provider=self.provider,
            name='GPT-4o',
            model_id='gpt-4o',
            input_price_per_1m_tokens=Decimal('5.000000'),
            output_price_per_1m_tokens=Decimal('15.000000'),
        )
        defaults.update(kwargs)
        return AIModel.objects.create(**defaults)

    def test_str_representation(self):
        m = self._make_model()
        self.assertIn('gpt-4o', str(m))
        self.assertIn('OpenAI Test', str(m))

    def test_default_active_true(self):
        m = self._make_model()
        self.assertTrue(m.active)

    def test_cascade_delete_with_provider(self):
        m = self._make_model()
        self.provider.delete()
        self.assertFalse(AIModel.objects.filter(pk=m.pk).exists())


# ---------------------------------------------------------------------------
# AIJobsHistory Tests
# ---------------------------------------------------------------------------

class AIJobsHistoryModelTest(TestCase):
    def setUp(self):
        self.provider = AIProvider.objects.create(
            name='OpenAI Test', provider_type='OpenAI', api_key='sk-test'
        )
        self.model = AIModel.objects.create(
            provider=self.provider, name='GPT-4o', model_id='gpt-4o',
        )

    def _make_job(self, **kwargs):
        defaults = dict(provider=self.provider, model=self.model)
        defaults.update(kwargs)
        return AIJobsHistory.objects.create(**defaults)

    def test_default_status_pending(self):
        job = self._make_job()
        self.assertEqual(job.status, AIJobsHistory.Status.PENDING)

    def test_str_representation(self):
        job = self._make_job()
        self.assertIn('Pending', str(job))

    def test_completed_status(self):
        job = self._make_job(
            status=AIJobsHistory.Status.COMPLETED,
            input_tokens=100,
            output_tokens=50,
            costs=Decimal('0.00175'),
            duration_ms=320,
        )
        self.assertEqual(job.status, AIJobsHistory.Status.COMPLETED)
        self.assertEqual(job.input_tokens, 100)
        self.assertEqual(job.costs, Decimal('0.00175'))

    def test_null_tokens_allowed(self):
        job = self._make_job()
        self.assertIsNone(job.input_tokens)
        self.assertIsNone(job.output_tokens)
        self.assertIsNone(job.costs)


# ---------------------------------------------------------------------------
# Pricing Tests
# ---------------------------------------------------------------------------

class PricingTest(TestCase):
    def test_calculates_cost_correctly(self):
        from core.services.ai.pricing import calculate_cost
        cost = calculate_cost(1000, 500, Decimal('5.0'), Decimal('15.0'))
        expected = Decimal('1000') / Decimal('1_000_000') * Decimal('5.0') + \
                   Decimal('500') / Decimal('1_000_000') * Decimal('15.0')
        self.assertEqual(cost, expected)

    def test_returns_none_when_tokens_missing(self):
        from core.services.ai.pricing import calculate_cost
        self.assertIsNone(calculate_cost(None, 500, Decimal('5.0'), Decimal('15.0')))
        self.assertIsNone(calculate_cost(1000, None, Decimal('5.0'), Decimal('15.0')))

    def test_returns_none_when_prices_missing(self):
        from core.services.ai.pricing import calculate_cost
        self.assertIsNone(calculate_cost(1000, 500, None, Decimal('15.0')))
        self.assertIsNone(calculate_cost(1000, 500, Decimal('5.0'), None))


# ---------------------------------------------------------------------------
# AIRouter Tests (mocked provider)
# ---------------------------------------------------------------------------

class AIRouterTest(TestCase):
    def setUp(self):
        self.provider_record = AIProvider.objects.create(
            name='OpenAI Test', provider_type='OpenAI', api_key='sk-test',
        )
        self.ai_model = AIModel.objects.create(
            provider=self.provider_record,
            name='GPT-4o',
            model_id='gpt-4o',
            input_price_per_1m_tokens=Decimal('5.0'),
            output_price_per_1m_tokens=Decimal('15.0'),
            active=True,
        )

    def _mock_provider_response(self):
        from core.services.ai.schemas import ProviderResponse
        return ProviderResponse(
            text='Hello, world!',
            raw=object(),
            input_tokens=10,
            output_tokens=5,
        )

    def test_chat_returns_ai_response(self):
        from core.services.ai.router import AIRouter
        from core.services.ai.schemas import AIResponse

        router = AIRouter()
        mock_resp = self._mock_provider_response()

        with patch.object(router, '_build_provider') as mock_build:
            mock_prov = MagicMock()
            mock_prov.chat.return_value = mock_resp
            mock_build.return_value = mock_prov

            result = router.chat(messages=[{'role': 'user', 'content': 'Hi'}])

        self.assertIsInstance(result, AIResponse)
        self.assertEqual(result.text, 'Hello, world!')
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.model, 'gpt-4o')
        self.assertEqual(result.provider, 'OpenAI')

    def test_chat_creates_completed_job(self):
        from core.services.ai.router import AIRouter

        router = AIRouter()
        mock_resp = self._mock_provider_response()

        with patch.object(router, '_build_provider') as mock_build:
            mock_prov = MagicMock()
            mock_prov.chat.return_value = mock_resp
            mock_build.return_value = mock_prov

            router.chat(messages=[{'role': 'user', 'content': 'Hi'}])

        job = AIJobsHistory.objects.filter(status=AIJobsHistory.Status.COMPLETED).first()
        self.assertIsNotNone(job)
        self.assertEqual(job.input_tokens, 10)
        self.assertEqual(job.output_tokens, 5)
        self.assertIsNotNone(job.costs)
        self.assertIsNotNone(job.duration_ms)

    def test_generate_shortcut(self):
        from core.services.ai.router import AIRouter

        router = AIRouter()
        mock_resp = self._mock_provider_response()

        with patch.object(router, '_build_provider') as mock_build:
            mock_prov = MagicMock()
            mock_prov.chat.return_value = mock_resp
            mock_build.return_value = mock_prov

            result = router.generate(prompt='Say hello.')

        self.assertEqual(result.text, 'Hello, world!')

    def test_chat_logs_error_on_failure(self):
        from core.services.ai.router import AIRouter

        router = AIRouter()

        with patch.object(router, '_build_provider') as mock_build:
            mock_prov = MagicMock()
            mock_prov.chat.side_effect = RuntimeError('API error')
            mock_build.return_value = mock_prov

            with self.assertRaises(RuntimeError):
                router.chat(messages=[{'role': 'user', 'content': 'Hi'}])

        job = AIJobsHistory.objects.filter(status=AIJobsHistory.Status.ERROR).first()
        self.assertIsNotNone(job)
        self.assertIn('API error', job.error_message)

    def test_raises_when_no_active_model(self):
        from core.services.ai.router import AIRouter
        from core.services.base import ServiceNotConfigured

        AIModel.objects.all().update(active=False)
        router = AIRouter()
        with self.assertRaises(ServiceNotConfigured):
            router.chat(messages=[{'role': 'user', 'content': 'Hi'}])

    def test_routing_by_provider_type(self):
        from core.services.ai.router import AIRouter

        router = AIRouter()
        mock_resp = self._mock_provider_response()

        with patch.object(router, '_build_provider') as mock_build:
            mock_prov = MagicMock()
            mock_prov.chat.return_value = mock_resp
            mock_build.return_value = mock_prov

            result = router.chat(
                messages=[{'role': 'user', 'content': 'Hi'}],
                provider_type='OpenAI',
            )

        self.assertEqual(result.provider, 'OpenAI')


# ---------------------------------------------------------------------------
# Page Service Tests
# ---------------------------------------------------------------------------

class PageServiceTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(key='blog', title='Blog', slug='blog', order=0)

    def test_create_page_basic(self):
        from core.services.page_service import create_page
        page = create_page(category=self.cat, title='Hello World')
        self.assertEqual(page.title, 'Hello World')
        self.assertEqual(page.slug, 'hello-world')
        self.assertEqual(page.category, self.cat)

    def test_create_page_auto_slug(self):
        from core.services.page_service import create_page
        page = create_page(category=self.cat, title='Test Page')
        self.assertEqual(page.slug, 'test-page')

    def test_create_page_custom_slug(self):
        from core.services.page_service import create_page
        page = create_page(category=self.cat, title='Test Page', slug='custom-slug')
        self.assertEqual(page.slug, 'custom-slug')

    def test_create_page_auto_slug_uniqueness(self):
        from core.services.page_service import create_page
        p1 = create_page(category=self.cat, title='Duplicate')
        p2 = create_page(category=self.cat, title='Duplicate')
        self.assertNotEqual(p1.slug, p2.slug)
        self.assertEqual(p2.slug, 'duplicate-1')

    def test_create_page_sanitizes_html(self):
        from core.services.page_service import create_page
        dirty = '<p>Safe</p><script>alert("xss")</script>'
        page = create_page(category=self.cat, title='HTML Test', content_html=dirty)
        self.assertIn('<p>Safe</p>', page.content_html)
        self.assertNotIn('<script>', page.content_html)

    def test_create_page_strips_disallowed_tags(self):
        from core.services.page_service import create_page
        page = create_page(
            category=self.cat, title='Img Test',
            content_html='<p>text</p><img src="x" onerror="alert(1)">',
        )
        self.assertNotIn('<img', page.content_html)

    def test_create_page_allows_anchor_with_href(self):
        from core.services.page_service import create_page
        page = create_page(
            category=self.cat, title='Link Test',
            content_html='<p><a href="https://example.com">link</a></p>',
        )
        self.assertIn('href="https://example.com"', page.content_html)

    def test_update_page(self):
        from core.services.page_service import create_page, update_page
        page = create_page(category=self.cat, title='Old Title')
        updated = update_page(page, title='New Title', status=Page.Status.PUBLISHED)
        self.assertEqual(updated.title, 'New Title')
        self.assertEqual(updated.status, Page.Status.PUBLISHED)

    def test_update_page_sanitizes_html(self):
        from core.services.page_service import create_page, update_page
        page = create_page(category=self.cat, title='Page')
        updated = update_page(
            page, title='Page', status=Page.Status.DRAFT,
            content_html='<p>ok</p><script>bad()</script>',
        )
        self.assertIn('<p>ok</p>', updated.content_html)
        self.assertNotIn('<script>', updated.content_html)


# ---------------------------------------------------------------------------
# PageDetailView Tests
# ---------------------------------------------------------------------------

class PageDetailViewTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(
            key='docs', title='Docs', slug='docs', order=0, is_visible=True,
        )
        self.page = Page.objects.create(
            category=self.cat, title='Intro', slug='intro',
            status=Page.Status.PUBLISHED, order_in_category=0,
        )

    def test_returns_200_for_published_page(self):
        response = self.client.get('/docs/intro/')
        self.assertEqual(response.status_code, 200)

    def test_uses_page_detail_template(self):
        response = self.client.get('/docs/intro/')
        self.assertTemplateUsed(response, 'core/page_detail.html')

    def test_returns_404_for_draft_page(self):
        draft = Page.objects.create(
            category=self.cat, title='Draft', slug='draft',
            status=Page.Status.DRAFT, order_in_category=1,
        )
        response = self.client.get(f'/docs/{draft.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_returns_404_for_invisible_category(self):
        cat2 = Category.objects.create(
            key='hidden', title='Hidden', slug='hidden', order=1, is_visible=False,
        )
        Page.objects.create(
            category=cat2, title='Page', slug='page',
            status=Page.Status.PUBLISHED, order_in_category=0,
        )
        response = self.client.get('/hidden/page/')
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# CMS Editor Views Tests
# ---------------------------------------------------------------------------

class CmsEditorPermissionTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.cat = Category.objects.create(
            key='test', title='Test', slug='test', order=0, is_visible=True,
        )
        self.admin = User.objects.create_superuser('admin', 'a@x.com', 'pass')
        self.regular = User.objects.create_user('user', 'u@x.com', 'pass')

    def test_create_redirects_anonymous_to_login(self):
        url = f'//_cms/pages/new/?category={self.cat.pk}'
        response = self.client.get(f'/_cms/pages/new/?category={self.cat.pk}')
        self.assertIn(response.status_code, [302, 403])

    def test_create_returns_403_for_unprivileged_user(self):
        self.client.login(username='user', password='pass')
        response = self.client.get(f'/_cms/pages/new/?category={self.cat.pk}')
        self.assertEqual(response.status_code, 403)

    def test_create_returns_200_for_superuser(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(f'/_cms/pages/new/?category={self.cat.pk}')
        self.assertEqual(response.status_code, 200)

    def test_create_post_creates_page_and_redirects(self):
        self.client.login(username='admin', password='pass')
        response = self.client.post(
            f'/_cms/pages/new/?category={self.cat.pk}',
            {
                'category': self.cat.pk,
                'title': 'My New Page',
                'slug': '',
                'summary': '',
                'status': 'published',
                'content_html': '<p>Hello</p>',
            },
        )
        self.assertEqual(response.status_code, 302)
        page = Page.objects.get(slug='my-new-page')
        self.assertEqual(page.title, 'My New Page')
        self.assertIn('<p>Hello</p>', page.content_html)

    def test_create_post_no_title_returns_form(self):
        self.client.login(username='admin', password='pass')
        response = self.client.post(
            f'/_cms/pages/new/?category={self.cat.pk}',
            {'category': self.cat.pk, 'title': '', 'status': 'draft', 'content_html': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cms/editor/page_form.html')

    def test_edit_returns_200_for_superuser(self):
        page = Page.objects.create(
            category=self.cat, title='Edit Me', slug='edit-me',
            status=Page.Status.DRAFT, order_in_category=0,
        )
        self.client.login(username='admin', password='pass')
        response = self.client.get(f'/_cms/pages/{page.pk}/edit/')
        self.assertEqual(response.status_code, 200)

    def test_edit_post_updates_page(self):
        page = Page.objects.create(
            category=self.cat, title='Old', slug='old',
            status=Page.Status.DRAFT, order_in_category=0,
        )
        self.client.login(username='admin', password='pass')
        response = self.client.post(
            f'/_cms/pages/{page.pk}/edit/',
            {
                'title': 'Updated Title',
                'slug': '',
                'summary': 'Updated summary',
                'status': 'published',
                'content_html': '<p>Updated content</p>',
            },
        )
        self.assertEqual(response.status_code, 302)
        page.refresh_from_db()
        self.assertEqual(page.title, 'Updated Title')
        self.assertEqual(page.status, Page.Status.PUBLISHED)

    def test_user_with_permission_can_access_create(self):
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(codename='manage_content')
        self.regular.user_permissions.add(perm)
        self.client.login(username='user', password='pass')
        response = self.client.get(f'/_cms/pages/new/?category={self.cat.pk}')
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Category Description Edit View Tests
# ---------------------------------------------------------------------------

class CategoryDescriptionEditViewTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.cat = Category.objects.create(
            key='desc-test', title='Desc Test', slug='desc-test', order=0, is_visible=True,
        )
        self.admin = User.objects.create_superuser('admin_desc', 'ad@x.com', 'pass')
        self.regular = User.objects.create_user('user_desc', 'ud@x.com', 'pass')
        self.url = f'/_cms/categories/{self.cat.pk}/description/'

    def test_anonymous_redirects_to_login(self):
        response = self.client.post(self.url, {'description': '<p>Hello</p>'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_unprivileged_user_gets_403(self):
        self.client.login(username='user_desc', password='pass')
        response = self.client.post(self.url, {'description': '<p>Hello</p>'})
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_save_description(self):
        self.client.login(username='admin_desc', password='pass')
        response = self.client.post(self.url, {'description': '<p>Hello World</p>'})
        self.assertEqual(response.status_code, 302)
        self.cat.refresh_from_db()
        self.assertIn('<p>Hello World</p>', self.cat.description)

    def test_description_is_sanitized(self):
        self.client.login(username='admin_desc', password='pass')
        self.client.post(self.url, {'description': '<p>Safe</p><script>alert(1)</script>'})
        self.cat.refresh_from_db()
        self.assertNotIn('<script>', self.cat.description)
        self.assertIn('<p>Safe</p>', self.cat.description)

    def test_redirect_goes_to_category_detail(self):
        self.client.login(username='admin_desc', password='pass')
        response = self.client.post(self.url, {'description': '<p>Test</p>'})
        self.assertRedirects(response, f'/{self.cat.slug}/', fetch_redirect_response=False)

    def test_user_with_permission_can_save_description(self):
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(codename='manage_content')
        self.regular.user_permissions.add(perm)
        self.client.login(username='user_desc', password='pass')
        response = self.client.post(self.url, {'description': '<p>Permitted</p>'})
        self.assertEqual(response.status_code, 302)
        self.cat.refresh_from_db()
        self.assertIn('<p>Permitted</p>', self.cat.description)

    def test_get_request_redirects_to_category(self):
        self.client.login(username='admin_desc', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.cat.slug, response['Location'])


# ==============================================================================
# AI Agent Optimization Tests
# ==============================================================================

class PageOptimizationViewsTest(TestCase):
    """Tests for page optimization views."""

    def setUp(self):
        """Set up test data."""
        # Create user with permissions
        from django.contrib.auth.models import User, Permission

        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        perm = Permission.objects.get(codename='manage_content')
        self.user.user_permissions.add(perm)

        # Create AI provider and model (required for router)
        self.provider = AIProvider.objects.create(
            name='Test OpenAI',
            provider_type='OpenAI',
            api_key='test-key-123',
            is_active=True
        )
        self.model = AIModel.objects.create(
            provider=self.provider,
            name='GPT-4',
            model_id='gpt-4.1',
            input_price_per_1m_tokens=10.0,
            output_price_per_1m_tokens=30.0,
            active=True
        )

        # Create category and page
        self.category = Category.objects.create(
            title='Test Category',
            slug='test-category',
            order=1
        )
        self.page = Page.objects.create(
            category=self.category,
            title='Test Page',
            slug='test-page',
            summary='This is a test summary with some typos.',
            content_html='<p>This is test content with errors.</p>',
            status=Page.Status.DRAFT
        )

        self.client.login(username='testuser', password='testpass123')

    @patch('core.cms_views.run_agent')
    def test_optimize_summary_success(self, mock_run_agent):
        """Test successful summary optimization."""
        from core.services.agents.service import AgentRunResult

        # Mock agent response
        mock_result = AgentRunResult(
            agent_id='text-optimization-agent',
            output_text='This is an optimized test summary without typos.',
            provider='OpenAI',
            model='gpt-4.1',
            input_tokens=10,
            output_tokens=15
        )
        mock_run_agent.return_value = mock_result

        url = reverse('cms:page-optimize-summary', kwargs={'pk': self.page.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('optimized_text', data)
        self.assertEqual(data['optimized_text'], 'This is an optimized test summary without typos.')

        # Verify page was updated
        self.page.refresh_from_db()
        self.assertEqual(self.page.summary, 'This is an optimized test summary without typos.')

        # Verify agent was called correctly
        mock_run_agent.assert_called_once()
        call_kwargs = mock_run_agent.call_args[1]
        self.assertEqual(call_kwargs['task_input'], 'This is a test summary with some typos.')
        self.assertEqual(call_kwargs['user'], self.user)

    @patch('core.cms_views.run_agent')
    def test_optimize_content_success(self, mock_run_agent):
        """Test successful content optimization."""
        from core.services.agents.service import AgentRunResult

        # Mock agent response
        mock_result = AgentRunResult(
            agent_id='text-optimization-agent',
            output_text='<p>This is optimized test content without errors.</p>',
            provider='OpenAI',
            model='gpt-4.1',
            input_tokens=15,
            output_tokens=20
        )
        mock_run_agent.return_value = mock_result

        url = reverse('cms:page-optimize-content', kwargs={'pk': self.page.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('optimized_text', data)

        # Verify page was updated
        self.page.refresh_from_db()
        self.assertIn('optimized test content', self.page.content_html)

    def test_optimize_summary_empty(self):
        """Test optimization with empty summary."""
        self.page.summary = ''
        self.page.save()

        url = reverse('cms:page-optimize-summary', kwargs={'pk': self.page.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)

    def test_optimize_content_empty(self):
        """Test optimization with empty content."""
        self.page.content_html = ''
        self.page.save()

        url = reverse('cms:page-optimize-content', kwargs={'pk': self.page.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)

    @patch('core.cms_views.run_agent')
    def test_optimize_summary_agent_error(self, mock_run_agent):
        """Test handling of agent execution error."""
        mock_run_agent.side_effect = Exception('AI service unavailable')

        url = reverse('cms:page-optimize-summary', kwargs={'pk': self.page.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('error', data)

    def test_optimize_requires_login(self):
        """Test that optimization requires authentication."""
        self.client.logout()

        url = reverse('cms:page-optimize-summary', kwargs={'pk': self.page.pk})
        response = self.client.post(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_optimize_requires_permission(self):
        """Test that optimization requires manage_content permission."""
        from django.contrib.auth.models import User

        # Create user without permission
        user_no_perm = User.objects.create_user(
            username='noperm',
            password='testpass123'
        )
        self.client.logout()
        self.client.login(username='noperm', password='testpass123')

        url = reverse('cms:page-optimize-summary', kwargs={'pk': self.page.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    def test_optimize_get_not_allowed(self):
        """Test that GET requests are not allowed."""
        url = reverse('cms:page-optimize-summary', kwargs={'pk': self.page.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)


class AgentServiceIntegrationTest(TestCase):
    """Integration tests for the agent service."""

    def test_agent_registry_loads_agents(self):
        """Test that agents are loaded from YAML files."""
        from core.services.agents.registry import get_agent

        agent = get_agent('text-optimization-agent')
        self.assertEqual(agent.agent_id, 'text-optimization-agent')
        self.assertEqual(agent.provider, 'OpenAI')
        self.assertIsNotNone(agent.role)
        self.assertIsNotNone(agent.task)

    def test_agent_not_found_raises_error(self):
        """Test that requesting non-existent agent raises error."""
        from core.services.agents.registry import get_agent, AgentNotFoundError

        with self.assertRaises(AgentNotFoundError):
            get_agent('non-existent-agent-xyz')

