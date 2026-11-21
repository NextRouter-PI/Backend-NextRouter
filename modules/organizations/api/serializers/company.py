from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from modules.accounts.api.serializers.user import UserReadSerializer
from modules.organizations.api.serializers.base import BaseProfileCreateSerializer, BaseProfilePatchSerializer
from modules.organizations.models.company import Company
from modules.organizations.services.profiles import create_company_profile, update_company_profile
from modules.organizations.validators.cnpj import validate_cnpj
from modules.uploads.api.serializers.document import DocumentSerializer
from modules.uploads.models.document import Document


class _CompanyPublicMixin(serializers.Serializer):
    profile_picture_url = serializers.SerializerMethodField()
    route_groups = serializers.SerializerMethodField()

    def get_profile_picture_url(self, instance) -> str | None:
        user = getattr(instance, 'user', None)
        picture = getattr(user, 'profile_picture', None) if user else None
        return picture.url if picture else None

    def get_route_groups(self, instance) -> list[dict]:
        groups = getattr(instance, 'matched_route_groups', None)
        if groups is None:
            groups = instance.route_groups.all()
        return [
            {
                'id': group.id,
                'name': group.name,
                'city': group.destination.city if group.destination else '',
                'state': group.destination.state if group.destination else '',
            }
            for group in groups
        ]


class CompanyPublicSerializer(_CompanyPublicMixin, ModelSerializer):
    class Meta:
        model = Company
        fields = ('id', 'trade_name', 'city', 'state', 'profile_picture_url', 'route_groups')


class CompanyListAndRetrieveSerializer(_CompanyPublicMixin, ModelSerializer):
    user_data = UserReadSerializer(source='user', read_only=True)
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

    def _can_view_private(self, instance) -> bool:
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return bool(
            user and (instance.user_id == user.pk or (user.is_staff and user.has_perm('organizations.view_company')))
        )

    def to_representation(self, instance):
        if not self._can_view_private(instance):
            return CompanyPublicSerializer(instance, context=self.context).data
        return super().to_representation(instance)


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

    def create(self, validated_data):
        return create_company_profile(validated_data, token_instance=self.context['token_instance'])


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

    def update(self, instance, validated_data):
        return update_company_profile(instance, validated_data)
