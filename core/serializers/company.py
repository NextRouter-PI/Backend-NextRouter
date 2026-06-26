from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models.company import Company
from uploader.models import Document
from uploader.serializers import DocumentUploadSerializer

from .user import User, UserCreateSerializer


class CompanyListAndRetrieveSerializer(ModelSerializer):
    company_id = serializers.IntegerField(source='user.id', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture')
    cep = serializers.CharField(source='user.cep')

    class Meta:
        model = Company
        fields = ['company_id', 'trade_name', 'profile_picture', 'cep']


class CompanyCreateSerializer(ModelSerializer):
    articles_of_association_document = DocumentUploadSerializer()
    state_operating_license_document = DocumentUploadSerializer()
    certificate_of_good_stading_document = DocumentUploadSerializer()
    user_data = UserCreateSerializer(source='user')

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        aoad_data = validated_data.pop('articles_of_association_document')
        sold_data = validated_data.pop('state_operating_license_document')
        cogsd_data = validated_data.pop('certificate_of_good_stading_document')
        user = User.objects.create_user(**user_data)
        aoad = Document.objects.create(**aoad_data)
        sold = Document.objects.create(**sold_data)
        cogsd = Document.objects.create(**cogsd_data)
        company = Company.objects.create(
            user=user,
            articles_of_association_document=aoad,
            state_operating_license_document=sold,
            certificate_of_good_stading_document=cogsd,
            **validated_data,
        )
        return company

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


class CompanyPatchSerializer(ModelSerializer):
    articles_of_association_document = DocumentUploadSerializer(required=False)
    state_operating_license_document = DocumentUploadSerializer(required=False)
    certificate_of_good_stading_document = DocumentUploadSerializer(required=False)
    user_data = UserCreateSerializer(source='user', required=False)

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

    def validate(self, attrs):
        forbidden_fields = ['is_approved', 'cnpj', 'user', 'cpf']

        if 'user_data' in self.initial_data and 'cpf' in self.initial_data['user_data']:
            raise serializers.ValidationError({'user_data': {'cpf': 'O CPF não pode ser modificado após a criação.'}})

        errors = {}
        for field in forbidden_fields:
            if field in self.initial_data:
                errors[field] = f"O campo '{field}' não pode ser modificado após a criação. Contate o suporte."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user_instance = instance.user
            for attr, value in user_data.items():
                setattr(user_instance, attr, value)
            user_instance.save()

        document_fields = [
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
        ]
        for doc_field in document_fields:
            doc_data = validated_data.pop(doc_field, None)
            if doc_data:
                doc_instance = getattr(instance, doc_field)
                for attr, value in doc_data.items():
                    setattr(doc_instance, attr, value)
                doc_instance.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
