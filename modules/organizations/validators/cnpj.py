from django.core.exceptions import ValidationError
from validate_docbr import CNPJ

_cnpj_validator = CNPJ()


def validate_cnpj(cnpj: str):
    if not isinstance(cnpj, str) or not _cnpj_validator.validate(cnpj):
        raise ValidationError('CNPJ inválido.')
