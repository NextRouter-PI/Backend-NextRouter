# Código adaptado de: https://www.devthru.com/guides/validation/cnpj/python

import re

from django.core.exceptions import ValidationError

CNPJ_LENGTH = 14
REMAINDER = 2


def validate_cnpj(cnpj: str):
    cnpj = re.sub(r'[^0-9]', '', cnpj)

    if len(cnpj) != CNPJ_LENGTH or len(set(cnpj)) == 1:
        raise ValidationError('CNPJ inválido.')

    weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_val = sum(int(cnpj[i]) * weights[i] for i in range(12))
    remainder = sum_val % 11
    digit_1 = 0 if remainder < REMAINDER else 11 - remainder

    if int(cnpj[12]) != digit_1:
        raise ValidationError('CNPJ inválido.')

    weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_val = sum(int(cnpj[i]) * weights[i] for i in range(13))
    remainder = sum_val % 11
    digit_2 = 0 if remainder < REMAINDER else 11 - remainder

    if not int(cnpj[13]) == digit_2:
        raise ValidationError('CNPJ inválido.')
