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
from uploader.serializers.document import DocumentUploadSerializer


class CompanyListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Company
        fields = ['user_data', 'trade_name', 'contact_phone', 'contact_email']


class CompanyCreateSerializer(BaseProfileCreateSerializer):
    articles_of_association_document = DocumentUploadSerializer()
    state_operating_license_document = DocumentUploadSerializer()
    certificate_of_good_stading_document = DocumentUploadSerializer()
    cnpj = serializers.CharField(validators=[validate_cnpj], required=True)

    class Meta:
        model = Company
        fields = [
            'user_data',
            'cnpj',
            'contact_phone',
            'contact_email',
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
            'trade_name',
            'legal_name',
            'state_registration',
        ]

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')

        doc_fields = [
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
        ]
        documents = {field: Document.objects.create(**validated_data.pop(field)) for field in doc_fields}

        user = self.create_user_instance(user_data)

        return Company.objects.create(user=user, **documents, **validated_data)


class CompanyPatchSerializer(BaseProfilePatchSerializer):
    articles_of_association_document = DocumentUploadSerializer(required=False)
    state_operating_license_document = DocumentUploadSerializer(required=False)
    certificate_of_good_stading_document = DocumentUploadSerializer(required=False)

    class Meta:
        model = Company
        fields = [
            'user_data',
            'contact_phone',
            'contact_email',
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
        ]

    def update(self, instance, validated_data):
        document_fields = [
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
        ]
        for doc_field in document_fields:
            doc_data = validated_data.pop(doc_field, None)
            if doc_data is not None:
                doc_instance = getattr(instance, doc_field)

                if doc_instance:
                    for attr, value in doc_data.items():
                        setattr(doc_instance, attr, value)
                    doc_instance.save()
                else:
                    new_doc = Document.objects.create(**doc_data)
                    setattr(instance, doc_field, new_doc)

        return super().update(instance, validated_data)
