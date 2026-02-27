from django.contrib import admin

from .models import NavigationItem, SiteSettings


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
