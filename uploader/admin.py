from django.contrib import admin

from uploader.models import Document, Image


@admin.register(Image)
class UploaderImageAdmin(admin.ModelAdmin):
    search_fields = ['user__name']
    actions = None
    readonly_fields = [
        'get_user',
        'attachment_key',
        'public_id',
        'uploaded_on',
    ]
    fieldsets = (
        (
            ('Identificação da imagem'),
            {
                'fields': (
                    'attachment_key',
                    'public_id',
                    'get_user',
                )
            },
        ),
        (
            ('Arquivo'),
            {
                'fields': (
                    'file',
                    'description',
                )
            },
        ),
        (('Datas'), {'fields': ('uploaded_on',)}),
    )

    list_display = [
        'get_user',
        'file',
    ]

    @admin.display(description='Usuário', ordering='user__name')
    def get_user(self, obj):
        try:
            return obj.user.name.title()
        except AttributeError:
            return 'Sem usuário'


admin.site.register(Document)
