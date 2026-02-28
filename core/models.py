import uuid
import logging

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class SiteSettings(models.Model):
    """Global site settings – singleton model."""

    site_name = models.CharField(max_length=120, default='PerculaCMS')
    tagline = models.CharField(max_length=255, blank=True, default='')
    base_url = models.URLField(blank=True, default='')
    logo = models.ImageField(upload_to='site/', blank=True, null=True)
    favicon = models.ImageField(upload_to='site/', blank=True, null=True)
    contact_email = models.EmailField(blank=True, default='')
    imprint = models.TextField(blank=True, default='')
    privacy_policy = models.TextField(blank=True, default='')
    footer_text = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        # Enforce singleton
        self.__class__.objects.exclude(pk=self.pk).delete()
        super().save(*args, **kwargs)
        logger.info('SiteSettings saved: %s', self.site_name)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class NavigationItem(models.Model):
    """Navigation menu items loaded from the database."""

    POSITION_CHOICES = [
        ('header', 'Header'),
        ('footer', 'Footer'),
    ]

    label = models.CharField(max_length=100)
    url = models.CharField(max_length=200)
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='header')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    open_in_new_tab = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'label']
        verbose_name = 'Navigation Item'
        verbose_name_plural = 'Navigation Items'

    def __str__(self):
        return f'{self.position} | {self.label}'


# ---------------------------------------------------------------------------
# Category (Navigation Node)
# ---------------------------------------------------------------------------

class Category(models.Model):
    """Primary navigation node. Represents a top-level menu entry."""

    class NavPlacement(models.TextChoices):
        HEADER = 'header', 'Header'
        FOOTER = 'footer', 'Footer'
        HIDDEN = 'hidden', 'Hidden'

    key = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    nav_placement = models.CharField(
        max_length=20,
        choices=NavPlacement.choices,
        default=NavPlacement.HEADER,
    )
    description = models.TextField(blank=True, default='')
    icon = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        indexes = [
            models.Index(fields=['nav_placement', 'is_visible', 'order']),
        ]

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class Page(models.Model):
    """A content page belonging to a Category."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='pages',
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    summary = models.TextField(blank=True, default='')
    template = models.CharField(max_length=100, blank=True, default='')
    order_in_category = models.PositiveIntegerField(default=0)
    # SEO
    seo_title = models.CharField(max_length=200, blank=True, default='')
    seo_description = models.TextField(blank=True, default='')
    og_image = models.CharField(max_length=500, blank=True, default='')
    og_image_asset = models.ForeignKey(
        'MediaAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='og_image_pages',
    )
    # Publishing
    published_at = models.DateTimeField(null=True, blank=True)
    # HTML content (Quill editor output, server-side sanitised)
    content_html = models.TextField(blank=True, default='')
    # Tags
    audience_tags = models.JSONField(default=list)
    intent_tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order_in_category']
        verbose_name = 'Page'
        verbose_name_plural = 'Pages'
        permissions = [
            ('manage_content', 'Can create and edit pages via the inline CMS editor'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['category', 'slug'], name='unique_page_slug_per_category'),
        ]
        indexes = [
            models.Index(fields=['category', 'status', 'order_in_category']),
            models.Index(fields=['status', 'published_at']),
        ]

    def __str__(self):
        return f'{self.category} / {self.title}'

    def clean(self):
        if self.parent_id and self.parent.category_id != self.category_id:
            raise ValidationError(
                'Parent page must belong to the same category as this page.'
            )

    def get_absolute_url(self):
        return f'/{self.category.slug}/{self.slug}'

    def publish(self):
        """Transition this page to published status and record the timestamp."""
        self.status = self.Status.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_at', 'updated_at'])


# ---------------------------------------------------------------------------
# PageBlock (Block-based Content)
# ---------------------------------------------------------------------------

class PageBlock(models.Model):
    """An ordered content block belonging to a Page."""

    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name='blocks',
    )
    type = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
    order = models.PositiveIntegerField(default=0)
    conditions = models.JSONField(default=dict)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Page Block'
        verbose_name_plural = 'Page Blocks'
        constraints = [
            models.UniqueConstraint(fields=['page', 'order'], name='unique_block_order_per_page'),
        ]
        indexes = [
            models.Index(fields=['page', 'order']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f'{self.page} – {self.type} [{self.order}]'


# ---------------------------------------------------------------------------
# Media Library
# ---------------------------------------------------------------------------

class MediaFolder(models.Model):
    """Optional folder hierarchy for organising media assets."""

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Media Folder'
        verbose_name_plural = 'Media Folders'
        constraints = [
            models.UniqueConstraint(fields=['parent', 'name'], name='unique_folder_name_per_parent'),
        ]
        indexes = [
            models.Index(fields=['parent', 'order']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """Prevent circular parent references and duplicate names within same parent."""
        # Check for duplicate name in the same parent (including root folders)
        qs = MediaFolder.objects.filter(parent=self.parent, name=self.name)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError('A folder with this name already exists in the same parent.')
        # Prevent circular parent reference
        if not self.pk:
            return
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk == self.pk:
                raise ValidationError('A folder cannot be its own ancestor.')
            ancestor = ancestor.parent


class MediaAsset(models.Model):
    """Central media asset model for images, videos, audio and documents."""

    class AssetType(models.TextChoices):
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'
        AUDIO = 'audio', 'Audio'
        DOCUMENT = 'document', 'Document'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ARCHIVED = 'archived', 'Archived'

    folder = models.ForeignKey(
        MediaFolder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assets',
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, default='')
    asset_type = models.CharField(
        max_length=20,
        choices=AssetType.choices,
        default=AssetType.OTHER,
    )
    file = models.FileField(upload_to='media_assets/')
    original_filename = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    checksum_sha256 = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Dimensions (image / video)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    # Duration (audio / video)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    # Document
    page_count = models.PositiveIntegerField(null=True, blank=True)
    # Accessibility / presentation
    alt_text = models.TextField(blank=True, default='')
    caption = models.TextField(blank=True, default='')
    # Thumbnail / preview (e.g. generated cover for PDF or video)
    preview_image_asset = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='preview_for',
    )
    tags = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Media Asset'
        verbose_name_plural = 'Media Assets'
        indexes = [
            models.Index(fields=['asset_type', 'status', 'created_at']),
            models.Index(fields=['folder', 'asset_type', 'created_at']),
        ]

    def __str__(self):
        return self.title


class MediaAssetUsage(models.Model):
    """Tracks where a MediaAsset is used (Page, PageBlock, …)."""

    asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.CASCADE,
        related_name='usages',
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    field = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Media Asset Usage'
        verbose_name_plural = 'Media Asset Usages'
        constraints = [
            models.UniqueConstraint(
                fields=['asset', 'content_type', 'object_id', 'field'],
                name='unique_asset_usage',
            ),
        ]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.asset} → {self.content_type} #{self.object_id} [{self.field}]'


# ---------------------------------------------------------------------------
# Redirect
# ---------------------------------------------------------------------------

class Redirect(models.Model):
    """HTTP redirect rules for managing slug changes and SEO-preserving redirects."""

    class StatusCode(models.IntegerChoices):
        PERMANENT = 301, '301 Permanent'
        TEMPORARY = 302, '302 Temporary'

    from_path = models.CharField(max_length=500)
    to_path = models.CharField(max_length=500)
    status_code = models.IntegerField(
        choices=StatusCode.choices,
        default=StatusCode.PERMANENT,
    )
    is_active = models.BooleanField(default=True)
    hit_count = models.PositiveIntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['from_path']
        verbose_name = 'Redirect'
        verbose_name_plural = 'Redirects'
        constraints = [
            models.UniqueConstraint(fields=['from_path'], name='unique_redirect_from_path'),
        ]
        indexes = [
            models.Index(fields=['is_active', 'from_path']),
        ]

    def __str__(self):
        return f'{self.from_path} → {self.to_path} [{self.status_code}]'

    def clean(self):
        if self.from_path and self.from_path == self.to_path:
            raise ValidationError('from_path and to_path must not be identical.')


# ---------------------------------------------------------------------------
# PageRevision
# ---------------------------------------------------------------------------

class PageRevision(models.Model):
    """Snapshot-based revision history for a Page (including its blocks)."""

    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name='revisions',
    )
    revision_no = models.PositiveIntegerField()
    snapshot = models.JSONField()
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='page_revisions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Page Revision'
        verbose_name_plural = 'Page Revisions'
        constraints = [
            models.UniqueConstraint(fields=['page', 'revision_no'], name='unique_page_revision_no'),
        ]
        indexes = [
            models.Index(fields=['page', 'created_at']),
        ]

    def __str__(self):
        return f'{self.page} – rev {self.revision_no}'


# ---------------------------------------------------------------------------
# Snippet
# ---------------------------------------------------------------------------

class Snippet(models.Model):
    """Reusable content fragments referenced across multiple pages."""

    key = models.CharField(max_length=200, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Snippet'
        verbose_name_plural = 'Snippets'
        indexes = [
            models.Index(fields=['is_active', 'type']),
        ]

    def __str__(self):
        return self.key


# ---------------------------------------------------------------------------
# Event Log (anonymous, session-based)
# ---------------------------------------------------------------------------

class VisitorSession(models.Model):
    """Anonymous visitor session for GDPR-friendly behavior tracking."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    consent = models.JSONField(default=dict)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    ip_hash = models.CharField(max_length=128, blank=True, default='')
    is_bot_suspected = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Visitor Session'
        verbose_name_plural = 'Visitor Sessions'
        indexes = [
            models.Index(fields=['last_seen_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return str(self.id)


# ---------------------------------------------------------------------------
# AI Core – Provider / Model / Jobs History
# ---------------------------------------------------------------------------

class AIProvider(models.Model):
    """Configuration record for an AI provider (OpenAI, Gemini, …)."""

    class ProviderType(models.TextChoices):
        OPENAI = 'OpenAI', 'OpenAI'
        GEMINI = 'Gemini', 'Gemini'
        CLAUDE = 'Claude', 'Claude'

    name = models.CharField(max_length=200)
    provider_type = models.CharField(
        max_length=20,
        choices=ProviderType.choices,
    )
    # API key stored as plain text; encrypt at-rest via DB/OS-level encryption or a
    # custom field wrapper.  Never logged or exposed in exceptions.
    api_key = models.CharField(max_length=500)
    organization_id = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Provider'
        verbose_name_plural = 'AI Providers'
        ordering = ['provider_type', 'name']

    def __str__(self):
        return f'{self.name} ({self.provider_type})'


class AIModel(models.Model):
    """A specific model offered by an AI provider."""

    provider = models.ForeignKey(
        AIProvider,
        on_delete=models.CASCADE,
        related_name='models',
    )
    name = models.CharField(max_length=200)
    model_id = models.CharField(max_length=200, help_text='Provider-side model identifier, e.g. gpt-4o')
    input_price_per_1m_tokens = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
        help_text='USD cost per 1 million input tokens',
    )
    output_price_per_1m_tokens = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
        help_text='USD cost per 1 million output tokens',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Model'
        verbose_name_plural = 'AI Models'
        ordering = ['provider', 'name']

    def __str__(self):
        return f'{self.provider.name} / {self.name} ({self.model_id})'


class AIJobsHistory(models.Model):
    """Audit log for every AI API call made through the AIRouter."""

    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        COMPLETED = 'Completed', 'Completed'
        ERROR = 'Error', 'Error'

    agent = models.CharField(max_length=200, default='core.ai')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ai_jobs',
    )
    provider = models.ForeignKey(
        AIProvider,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='jobs',
    )
    model = models.ForeignKey(
        AIModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='jobs',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    costs = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'AI Jobs History'
        verbose_name_plural = 'AI Jobs History'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['provider', 'model', 'status', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.agent} | {self.status} | {self.timestamp}'


class BehaviorEvent(models.Model):
    """A single tracked event within an anonymous visitor session."""

    session = models.ForeignKey(
        VisitorSession,
        on_delete=models.CASCADE,
        related_name='events',
    )
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-occurred_at']
        verbose_name = 'Behavior Event'
        verbose_name_plural = 'Behavior Events'
        indexes = [
            models.Index(fields=['session', 'occurred_at']),
            models.Index(fields=['event_type', 'occurred_at']),
        ]

    def __str__(self):
        return f'{self.event_type} @ {self.occurred_at}'
