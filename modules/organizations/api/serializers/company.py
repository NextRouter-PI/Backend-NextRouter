from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from modules.accounts.api.serializers.user import (
    BaseProfileCreateSerializer,
    BaseProfilePatchSerializer,
    UserListAndRetriveSerializer,
)
from modules.organizations.models.company import Company
from modules.organizations.validators.cnpj import validate_cnpj
from modules.uploads.api.serializers.document import DocumentSerializer
from modules.uploads.models.document import Document
from shared.geocoding import lookup_cep_brasilapi


class CompanyListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    route_groups = serializers.SerializerMethodField()
    articles_of_association_document_data = DocumentSerializer(
        source='articles_of_association_document', read_only=True
    )
    state_operating_license_document_data = DocumentSerializer(
        source='state_operating_license_document', read_only=True
    )
    certificate_of_good_stading_document_data = DocumentSerializer(
        source='certificate_of_good_stading_document', read_only=True
    )

    class Meta:
        model = Company
        fields = (
            'id',
            'user_data',
            'trade_name',
            'legal_name',
            'cnpj',
            'state_registration',
            'contact_phone',
            'contact_email',
            'cep',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'profile_picture_url',
            'route_groups',
            'latitude',
            'longitude',
            'geocoded_at',
            'is_approved',
            'review_status',
            'reviewed_at',
            'reviewed_by',
            'articles_of_association_document_data',
            'state_operating_license_document_data',
            'certificate_of_good_stading_document_data',
        )

    def get_profile_picture_url(self, instance) -> str | None:
        user = getattr(instance, 'user', None)
        picture = getattr(user, 'profile_picture', None) if user else None
        return picture.url if picture else None

    def get_route_groups(self, instance) -> list[dict]:
        groups = getattr(instance, 'matched_route_groups', None)
        if groups is None:
            groups = instance.route_groups.select_related('destination').order_by('name', 'id')
        return [
            {
                'id': group.id,
                'name': group.name,
                'city': group.destination.city if group.destination else '',
                'state': group.destination.state if group.destination else '',
            }
            for group in groups
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and (instance.user_id == user.pk or (user.is_staff and user.has_perm('organizations.view_company'))):
            return data
        return {
            key: data[key]
            for key in ('id', 'trade_name', 'city', 'state', 'profile_picture_url', 'route_groups')
        }


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
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False, allow_null=True)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False, allow_null=True)

    def validate_cnpj(self, value):
        cnpj = ''.join(filter(str.isdigit, value))
        if Company.objects.filter(cnpj=cnpj).exists():
            raise serializers.ValidationError('Já existe uma empresa cadastrada com este CNPJ.')
        return cnpj

    class Meta:
        model = Company
        fields = (
            'user_data',
            'trade_name',
            'contact_phone',
            'contact_email',
            'cnpj',
            'cep',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'latitude',
            'longitude',
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

        has_coords = validated_data.get('latitude') is not None and validated_data.get('longitude') is not None
        if has_coords:
            validated_data['geocoded_at'] = timezone.now()
        else:
            validated_data.pop('latitude', None)
            validated_data.pop('longitude', None)
            cep = validated_data.get('cep')
            if cep:
                cep_info = lookup_cep_brasilapi(cep)
                if cep_info and cep_info['latitude'] is not None and cep_info['longitude'] is not None:
                    validated_data['latitude'] = cep_info['latitude']
                    validated_data['longitude'] = cep_info['longitude']
                    validated_data['geocoded_at'] = timezone.now()

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
            'trade_name',
            'legal_name',
            'state_registration',
            'contact_phone',
            'contact_email',
            'cep',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'articles_of_association_document',
            'state_operating_license_document',
            'certificate_of_good_stading_document',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        initial_data = getattr(self, 'initial_data', {}) or {}
        if 'cnpj' in initial_data:
            raise serializers.ValidationError({
                'cnpj': 'Você não tem permissão para alterar o campo CNPJ. Contate o suporte.'
            })

        return attrs

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
