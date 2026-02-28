from django.contrib import admin
from django.utils.html import format_html
from django_json_widget.widgets import JSONEditorWidget

from .models import (
    AIJobsHistory,
    AIModel,
    AIProvider,
    BehaviorEvent,
    Category,
    MediaAsset,
    MediaAssetUsage,
    MediaFolder,
    NavigationItem,
    Page,
    PageBlock,
    PageRevision,
    Redirect,
    SiteSettings,
    Snippet,
    VisitorSession,
)


# ---------------------------------------------------------------------------
# JSON widget mixin – applies JSONEditorWidget to all JSONFields
# ---------------------------------------------------------------------------

class JSONWidgetMixin:
    """Mixin that replaces all JSONField widgets with the CodeMirror editor."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from django.db.models import JSONField as DjangoJSONField
        if isinstance(db_field, DjangoJSONField):
            kwargs['widget'] = JSONEditorWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)


# ---------------------------------------------------------------------------
# SiteSettings / NavigationItem (existing, unchanged)
# ---------------------------------------------------------------------------

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'base_url', 'contact_email', 'updated_at')
    fieldsets = (
        ('General', {'fields': ('site_name', 'tagline', 'base_url', 'logo', 'favicon')}),
        ('Contact', {'fields': ('contact_email',)}),
        ('Legal', {'fields': ('imprint', 'privacy_policy')}),
        ('Footer', {'fields': ('footer_text',)}),
    )


@admin.register(NavigationItem)
class NavigationItemAdmin(admin.ModelAdmin):
    list_display = ('label', 'url', 'position', 'parent', 'order', 'is_active')
    list_filter = ('position', 'is_active')
    list_editable = ('order', 'is_active')
    ordering = ('position', 'order', 'label')


# ---------------------------------------------------------------------------
# 1) Category
# ---------------------------------------------------------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'title', 'slug', 'key', 'nav_placement', 'is_visible', 'updated_at')
    list_display_links = ('title',)
    list_editable = ('order', 'is_visible', 'nav_placement')
    list_filter = ('nav_placement', 'is_visible')
    search_fields = ('title', 'slug', 'key')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basics', {'fields': ('title', 'slug', 'key', 'description')}),
        ('Navigation', {'fields': ('nav_placement', 'order', 'is_visible', 'icon')}),
        ('Meta', {'fields': ('created_at', 'updated_at')}),
    )


# ---------------------------------------------------------------------------
# 2) Page (with PageBlock inline and optional MediaAssetUsage inline)
# ---------------------------------------------------------------------------

class PageBlockInline(JSONWidgetMixin, admin.StackedInline):
    model = PageBlock
    extra = 0
    fields = ('order', 'type', 'is_enabled', 'data', 'conditions')
    ordering = ('order',)
    classes = ('collapse',)


class MediaAssetUsageInline(admin.TabularInline):
    model = MediaAssetUsage
    extra = 0
    readonly_fields = ('asset', 'content_type', 'object_id', 'field', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Page)
class PageAdmin(JSONWidgetMixin, admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'order_in_category', 'published_at', 'updated_at')
    list_editable = ('status', 'order_in_category')
    list_filter = ('category', 'status')
    search_fields = ('title', 'slug', 'summary')
    date_hierarchy = 'updated_at'
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at')
    inlines = [PageBlockInline]
    fieldsets = (
        ('Basics', {'fields': ('title', 'slug', 'category', 'parent', 'summary', 'template')}),
        ('Content', {'fields': ('content_html',)}),
        ('Publishing', {'fields': ('status', 'published_at')}),
        ('SEO', {'fields': ('seo_title', 'seo_description', 'og_image', 'og_image_asset')}),
        ('Cognitive Tags', {'fields': ('audience_tags', 'intent_tags')}),
        ('Meta', {'fields': ('created_at', 'updated_at')}),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'parent':
            # Restrict parent choices to pages within the same category
            obj_id = request.resolver_match.kwargs.get('object_id')
            if obj_id:
                try:
                    obj = Page.objects.get(pk=obj_id)
                    kwargs['queryset'] = Page.objects.filter(
                        category=obj.category
                    ).exclude(pk=obj_id)
                except Page.DoesNotExist:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ---------------------------------------------------------------------------
# 3) PageBlock (optional standalone debug view)
# ---------------------------------------------------------------------------

@admin.register(PageBlock)
class PageBlockAdmin(JSONWidgetMixin, admin.ModelAdmin):
    list_display = ('page', 'type', 'order', 'is_enabled', 'updated_at')
    list_filter = ('type', 'is_enabled')
    search_fields = ('page__title',)
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# 4) Snippet
# ---------------------------------------------------------------------------

@admin.register(Snippet)
class SnippetAdmin(JSONWidgetMixin, admin.ModelAdmin):
    list_display = ('key', 'title', 'type', 'is_active', 'updated_at')
    list_filter = ('type', 'is_active')
    search_fields = ('key', 'title')
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# 5) Redirect
# ---------------------------------------------------------------------------

@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ('from_path', 'to_path', 'status_code', 'is_active', 'hit_count', 'last_hit_at', 'updated_at')
    list_filter = ('is_active', 'status_code')
    search_fields = ('from_path', 'to_path')
    list_editable = ('is_active', 'status_code')
    readonly_fields = ('hit_count', 'last_hit_at', 'created_at', 'updated_at')


# ---------------------------------------------------------------------------
# 6) MediaFolder
# ---------------------------------------------------------------------------

@admin.register(MediaFolder)
class MediaFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'order', 'updated_at')
    list_filter = ('parent',)
    search_fields = ('name',)
    list_editable = ('order',)
    ordering = ('parent__name', 'order', 'name')
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# 7) MediaAsset (with image thumbnail preview)
# ---------------------------------------------------------------------------

@admin.register(MediaAsset)
class MediaAssetAdmin(JSONWidgetMixin, admin.ModelAdmin):
    list_display = ('preview_thumbnail', 'title', 'asset_type', 'mime_type', 'file_size', 'folder', 'created_at')
    list_filter = ('asset_type', 'folder', 'status')
    search_fields = ('title', 'original_filename', 'mime_type')
    readonly_fields = (
        'preview_thumbnail', 'original_filename', 'mime_type', 'file_size',
        'checksum_sha256', 'created_at', 'updated_at',
    )
    autocomplete_fields = ('folder',)
    fieldsets = (
        ('File', {'fields': ('file', 'title', 'folder', 'status')}),
        ('Metadata', {
            'fields': (
                'original_filename', 'mime_type', 'file_size', 'checksum_sha256',
                'width', 'height', 'duration_seconds', 'page_count',
            ),
        }),
        ('Accessibility', {'fields': ('alt_text', 'caption', 'tags')}),
        ('Preview', {'fields': ('preview_thumbnail', 'preview_image_asset')}),
        ('Meta', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Preview')
    def preview_thumbnail(self, obj):
        if obj.asset_type == MediaAsset.AssetType.IMAGE and obj.file:
            return format_html(
                '<img src="{}" style="max-height:60px;max-width:100px;object-fit:contain;" />',
                obj.file.url,
            )
        return '-'


# ---------------------------------------------------------------------------
# 8) MediaAssetUsage
# ---------------------------------------------------------------------------

@admin.register(MediaAssetUsage)
class MediaAssetUsageAdmin(admin.ModelAdmin):
    list_display = ('asset', 'content_type', 'object_id', 'field', 'created_at')
    list_filter = ('content_type',)
    search_fields = ('asset__title', 'field')
    readonly_fields = ('asset', 'content_type', 'object_id', 'field', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# 9) PageRevision (read-mostly)
# ---------------------------------------------------------------------------

@admin.register(PageRevision)
class PageRevisionAdmin(JSONWidgetMixin, admin.ModelAdmin):
    list_display = ('page', 'revision_no', 'created_at', 'created_by', 'note')
    list_filter = ('page__category', 'created_by')
    search_fields = ('page__title', 'note')
    readonly_fields = ('page', 'revision_no', 'snapshot', 'created_at', 'created_by', 'note')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# 10) VisitorSession + BehaviorEvent (read-only)
# ---------------------------------------------------------------------------

@admin.register(VisitorSession)
class VisitorSessionAdmin(JSONWidgetMixin, admin.ModelAdmin):
    list_display = ('id', 'created_at', 'last_seen_at', 'is_bot_suspected')
    readonly_fields = ('id', 'created_at', 'last_seen_at', 'consent', 'user_agent', 'ip_hash', 'is_bot_suspected')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BehaviorEvent)
class BehaviorEventAdmin(JSONWidgetMixin, admin.ModelAdmin):
    list_display = ('occurred_at', 'event_type', 'session', 'short_payload')
    list_filter = ('event_type',)
    search_fields = ('event_type',)
    date_hierarchy = 'occurred_at'
    readonly_fields = ('session', 'event_type', 'payload', 'occurred_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Payload (short)')
    def short_payload(self, obj):
        text = str(obj.payload)
        return text[:80] + '…' if len(text) > 80 else text


# ---------------------------------------------------------------------------
# 11) AI Provider / Model / JobsHistory
# ---------------------------------------------------------------------------

@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'is_active', 'updated_at')
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('provider', 'name', 'model_id', 'active', 'input_price_per_1m_tokens', 'output_price_per_1m_tokens', 'updated_at')
    list_filter = ('provider', 'active')
    search_fields = ('name', 'model_id')
    list_editable = ('active',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIJobsHistory)
class AIJobsHistoryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'agent', 'user', 'provider', 'model', 'status', 'costs', 'duration_ms')
    list_filter = ('provider', 'model', 'status', 'user')
    search_fields = ('agent',)
    date_hierarchy = 'timestamp'
    readonly_fields = (
        'agent', 'user', 'provider', 'model', 'status', 'client_ip',
        'input_tokens', 'output_tokens', 'costs', 'timestamp', 'duration_ms',
        'error_message',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
