from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from .models import (
    NavigationItem, SiteSettings, Category, Page, PageBlock,
    MediaFolder, MediaAsset, MediaAssetUsage,
    Redirect, PageRevision, Snippet, VisitorSession, BehaviorEvent,
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
