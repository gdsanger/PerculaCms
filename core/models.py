import logging

from django.db import models

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
