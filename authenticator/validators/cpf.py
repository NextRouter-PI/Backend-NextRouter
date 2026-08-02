from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

CPF_LENGTH = 11
MODULE_11_MULTIPLIER = 10
MODULE_11_DIVISOR = 11
MAX_DIGIT_VALUE = 10

# TODO - Revisar código


def validate_cpf(value):
    cpf = str(value)

    if len(cpf) != CPF_LENGTH or not cpf.isdigit():
        raise ValidationError(_('O CPF deve conter exatamente 11 dígitos numéricos.'), code='invalid_cpf_format')

    if cpf == cpf[0] * CPF_LENGTH:
        raise ValidationError(_('%(value)s não é um CPF válido.'), params={'value': value}, code='invalid_cpf')

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * MODULE_11_MULTIPLIER) % MODULE_11_DIVISOR
    digito_1 = resto if resto < MAX_DIGIT_VALUE else 0

    if int(cpf[9]) != digito_1:
        raise ValidationError(_('%(value)s não é um CPF válido.'), params={'value': value}, code='invalid_cpf')

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * MODULE_11_MULTIPLIER) % MODULE_11_DIVISOR
    digito_2 = resto if resto < MAX_DIGIT_VALUE else 0

    if int(cpf[10]) != digito_2:
        raise ValidationError(_('%(value)s não é um CPF válido.'), params={'value': value}, code='invalid_cpf')
