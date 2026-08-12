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
            'item_description',
            'travel',
        )
