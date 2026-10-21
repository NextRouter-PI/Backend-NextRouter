from typing import ClassVar

from django.conf import settings
from rest_framework import serializers

from uploader.helpers.files import CONTENT_TYPE_JPG, CONTENT_TYPE_PNG, get_content_type
from uploader.models import Image


class ImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = (
            'attachment_key',
            'file',
            'description',
            'uploaded_on',
            'url',
        )
        read_only_fields = (
            'attachment_key',
            'uploaded_on',
            'url',
            'description',
        )
        extra_kwargs: ClassVar[dict] = {'file': {'write_only': True}}

    def validate_file(self, value):
        if value.size > settings.MAX_IMAGE_UPLOAD_SIZE:
            raise serializers.ValidationError('A imagem deve ter no máximo 5 MB.')

        # Verifica o conteúdo real do arquivo, não o Content-Type informado pelo cliente.
        if get_content_type(value) not in {CONTENT_TYPE_JPG, CONTENT_TYPE_PNG}:
            raise serializers.ValidationError('Imagem inválida ou corrompida. Envie um arquivo JPG ou PNG.')
        return value


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = (
            'url',
            'description',
            'uploaded_on',
        )
        read_only_fields = (
            'url',
            'attachment_key',
            'uploaded_on',
        )

    def create(self, validated_data):
        raise NotImplementedError('Use ImageUploadSerializer to create images.')
