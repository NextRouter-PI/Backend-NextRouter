"""Entradas explícitas: campo desconhecido/protegido é erro, nunca ignorado."""

from rest_framework import serializers


class StrictInputMixin:
    def to_internal_value(self, data):
        if isinstance(data, dict):
            forbidden = set(data) - {name for name, field in self.fields.items() if not field.read_only}
            if forbidden:
                raise serializers.ValidationError(dict.fromkeys(sorted(forbidden), 'Campo desconhecido ou protegido.'))
        return super().to_internal_value(data)


class InputSerializer(StrictInputMixin, serializers.Serializer):
    pass


class InputModelSerializer(StrictInputMixin, serializers.ModelSerializer):
    pass


class EmptyInput(InputSerializer):
    pass


class RevisionInput(InputSerializer):
    expected_revision = serializers.IntegerField(min_value=1)


class ReasonInput(InputSerializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


class OperationInput(InputSerializer):
    operation_id = serializers.UUIDField()


class DomainErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    errors = serializers.JSONField(required=False)
