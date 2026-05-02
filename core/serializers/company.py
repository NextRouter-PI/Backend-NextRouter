from rest_framework.serializers import ModelSerializer

from core.models.company import Company
from uploader.models import Document
from uploader.serializers import DocumentUploadSerializer

from .user import User, UserRegistrationSerializer


class CompanySerializer(ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'


class CompanyRegistrationSerializer(ModelSerializer):
    articles_of_association_document = DocumentUploadSerializer(source='aoad_doc', write_only=True)
    state_operating_license_document = DocumentUploadSerializer(source='sold_doc', write_only=True)
    certificate_of_good_stading_documen = DocumentUploadSerializer(source='cogsd_doc', write_only=True)
    user_data = UserRegistrationSerializer(source='user', write_only=True)

    class Meta:
        model = Company
        fields = [
            'user_data',
            'cnpj',
            'contact_phone',
            'contact_email',
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_documen',
        ]

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        articles_of_association_document = validated_data.pop('aoad_doc')
        state_operating_license_document = validated_data.pop('sold_doc')
        certificate_of_good_stading_document = validated_data.pop('cogsd_doc')
        user = User.objects.create_user(**user_data)
        aoad = Document.objects.create(**articles_of_association_document)
        sold = Document.objects.create(**state_operating_license_document)
        cogsd = Document.objects.create(**certificate_of_good_stading_document)
        company = Company.objects.create(
            user=user,
            articles_of_association_document=aoad,
            state_operating_license_document=sold,
            certificate_of_good_stading_document=cogsd,
            **validated_data,
        )
        return company
