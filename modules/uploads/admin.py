from django.contrib import admin

from .models import Document, Image


class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('description', 'file', 'uploaded_on')
    search_fields = ('description', 'file', 'attachment_key', 'public_id')
    list_filter = ('uploaded_on',)
    readonly_fields = ('attachment_key', 'public_id', 'uploaded_on')
    date_hierarchy = 'uploaded_on'
    actions = None
    fieldsets = (
        ('Arquivo', {'fields': ('file', 'description')}),
        ('Identificação', {'fields': ('attachment_key', 'public_id', 'uploaded_on'), 'classes': ('collapse',)}),
    )


@admin.register(Image)
class ImageAdmin(AttachmentAdmin):
    list_display = ('description', 'get_user', 'file', 'uploaded_on')
    search_fields = (*AttachmentAdmin.search_fields, 'user__name', 'user__email')
    list_select_related = ('user',)

    @admin.display(description='Usuário', ordering='user__name')
    def get_user(self, obj):
        return getattr(obj, 'user', None) or 'Sem usuário'


@admin.register(Document)
class DocumentAdmin(AttachmentAdmin):
    pass
