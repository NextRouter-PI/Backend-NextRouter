from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models.company import Company
from uploader.models import Document
from uploader.serializers import DocumentUploadSerializer

from .user import User, UserCreateSerializer, UserListAndRetriveSerializer


class CompanyListAndRetrieveSerializer(ModelSerializer):
    company_id = serializers.IntegerField(source='user.id', read_only=True)
    name = serializers.CharField(source='user.name')
    profile_picture = serializers.ImageField(source='user.profile_picture')
    cep = serializers.CharField(source='user.cep')

    class Meta:
        model = Company
        fields = ['company_id', 'name', 'profile_picture', 'contact_phone', 'contact_email', 'cep']


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
        ]


class CompanyPatchSerializer(CompanyListAndRetrieveSerializer):
    class Meta:
        model = Company
        fields = ['company_id','name', 'profile_picture', 'contact_phone', 'contact_email', 'cep']
