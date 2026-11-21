from django.core.exceptions import ValidationError
from validate_docbr import CPF

_cpf_validator = CPF()


def validate_cpf(cpf: str):
    if not isinstance(cpf, str) or not _cpf_validator.validate(cpf):
        raise ValidationError('CPF inválido.')
