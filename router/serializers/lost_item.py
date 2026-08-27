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

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LostItemPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItem
        fields = ('item_description',)
