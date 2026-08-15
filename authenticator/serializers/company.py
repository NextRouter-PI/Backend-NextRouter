from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from authenticator.models.company import Company
from authenticator.serializers.user import (
    BaseProfileCreateSerializer,
    BaseProfilePatchSerializer,
    UserListAndRetriveSerializer,
)
from authenticator.validators.cnpj import validate_cnpj
from uploader.models.document import Document


class CompanyListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Company
        fields = (
            'id',
            'user_data',
            'trade_name',
            'contact_phone',
            'contact_email',
        )


class CompanyCreateSerializer(BaseProfileCreateSerializer):
    articles_of_association_document = serializers.SlugRelatedField(
        slug_field='attachment_key', queryset=Document.objects.all()
    )
    state_operating_license_document = serializers.SlugRelatedField(
        slug_field='attachment_key', queryset=Document.objects.all()
    )
    certificate_of_good_stading_document = serializers.SlugRelatedField(
        slug_field='attachment_key', queryset=Document.objects.all()
    )
    cnpj = serializers.CharField(validators=[validate_cnpj], required=True)

    class Meta:
        model = Company
        fields = (
            'user_data',
            'trade_name',
            'contact_phone',
            'contact_email',
            'cnpj',
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
            'legal_name',
            'state_registration',
        )

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = self.create_user_instance(user_data)

        return Company.objects.create(user=user, **validated_data)


class CompanyPatchSerializer(BaseProfilePatchSerializer):
    articles_of_association_document = serializers.SlugRelatedField(
        slug_field='attachment_key',
        queryset=Document.objects.all(),
        required=False,
        allow_null=True,
    )
    state_operating_license_document = serializers.SlugRelatedField(
        slug_field='attachment_key',
        queryset=Document.objects.all(),
        required=False,
        allow_null=True,
    )
    certificate_of_good_stading_document = serializers.SlugRelatedField(
        slug_field='attachment_key',
        queryset=Document.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Company
        fields = (
            'user_data',
            'contact_phone',
            'contact_email',
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        document_fields = [
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
        ]

        for doc_field in document_fields:
            if doc_field in validated_data:
                new_doc_instance = validated_data.pop(doc_field)
                old_doc_instance = getattr(instance, doc_field, None)
                if old_doc_instance and old_doc_instance != new_doc_instance:
                    old_doc_instance.delete()

                setattr(instance, doc_field, new_doc_instance)

        return super().update(instance, validated_data)
