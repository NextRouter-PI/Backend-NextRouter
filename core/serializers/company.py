from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import Empresa, User


class EmpresaSerializer(ModelSerializer):
    class Meta:
        model = Empresa
        fields = "__all__"


class RegistroEmpresaSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    razao_social = serializers.CharField(required=False)
    cnpj = serializers.CharField(required=False)
    inscricao_estadual = serializers.CharField(required=False)
    responsavel_nome = serializers.CharField(required=False)
    responsavel_cpf = serializers.CharField(required=False)
    telefone_comercial = serializers.CharField(required=False)
    endereco = serializers.CharField(required=False)
    cidade = serializers.CharField(required=False)
    estado = serializers.CharField(required=False)
    cep = serializers.CharField(required=False)
    valor_mensal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "password",
            "razao_social",
            "cnpj",
            "inscricao_estadual",
            "responsavel_nome",
            "responsavel_cpf",
            "telefone_comercial",
            "endereco",
            "cidade",
            "estado",
            "cep",
            "valor_mensal",
        ]

    def create(self, validated_data):
        razao_social = validated_data.pop("razao_social", None)
        cnpj = validated_data.pop("cnpj", None)
        inscricao_estadual = validated_data.pop("inscricao_estadual", None)
        responsavel_nome = validated_data.pop("responsavel_nome", None)
        responsavel_cpf = validated_data.pop("responsavel_cpf", None)
        telefone_comercial = validated_data.pop("telefone_comercial", None)
        endereco = validated_data.pop("endereco", None)
        cidade = validated_data.pop("cidade", None)
        estado = validated_data.pop("estado", None)
        cep = validated_data.pop("cep", None)
        valor_mensal = validated_data.pop("valor_mensal", None)

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data.get("name"),
            type="Empresa",
        )

        Empresa.objects.create(
            user=user,
            razao_social=razao_social,
            cnpj=cnpj,
            inscricao_estadual=inscricao_estadual,
            responsavel_nome=responsavel_nome,
            responsavel_cpf=responsavel_cpf,
            telefone_comercial=telefone_comercial,
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep,
            valor_mensal=valor_mensal,
        )

        return user
