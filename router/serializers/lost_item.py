from rest_framework import serializers

from router.models.lost_item import LostItem


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

        if user.is_staff or user.is_superuser:
            return travel

        participated = (
            travel.passenger_confirms.filter(user=user).exists()
            or travel.driver.user_id == user.id
            or travel.path.route_group.passengers.filter(user=user, is_approved=True).exists()
        )
        if not participated:
            raise serializers.ValidationError('Você não participou desta viagem.')

        return travel


class LostItemPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItem
        fields = ('item_description',)
