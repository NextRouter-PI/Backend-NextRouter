from rest_framework import serializers

from modules.transport.models.lost_item import LostItem
from modules.transport.models.travel import Travel


class LostItemListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItem
        fields = '__all__'


class LostItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItem
        fields = (
            'id',
            'item_description',
            'travel',
        )

    def validate_travel(self, travel):
        user = self.context['request'].user

        if travel.status != Travel.Status.FINISHED:
            raise serializers.ValidationError('Só é possível relatar objeto perdido em viagens encerradas.')

        if user.is_staff or user.is_superuser:
            return travel

        participated = travel.passenger_confirms.filter(user=user, confirm=True).exists() or (
            travel.driver.user_id == user.id and travel.driver.is_approved
        )
        if not participated:
            raise serializers.ValidationError('Você não participou desta viagem.')

        return travel


class LostItemPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItem
        fields = ('item_description', 'status')

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        instance = self.instance
        if instance and user and not (user.is_staff or user.is_superuser):
            is_owner = instance.user_id == user.pk
            is_company_or_driver = (
                instance.travel.company.user_id == user.pk and instance.travel.company.is_approved
            ) or (instance.travel.driver.user_id == user.pk and instance.travel.driver.is_approved)
            if 'item_description' in attrs and not is_owner:
                raise serializers.ValidationError({
                    'item_description': 'Apenas o autor do relato pode alterar a descrição do item.'
                })
            if (
                'status' in attrs
                and not is_company_or_driver
                and not (is_owner and attrs['status'] == LostItem.Status.RETURNED)
            ):
                raise serializers.ValidationError({
                    'status': 'Apenas a empresa ou o motorista da viagem pode atualizar este status.'
                })
        return attrs
