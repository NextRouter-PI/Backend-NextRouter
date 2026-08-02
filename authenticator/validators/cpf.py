# Código adaptado de: https://www.devthru.com/guides/validation/cpf/python


from django.core.exceptions import ValidationError

CPF_LENGTH = 11
MODULE_11_MULTIPLIER = 10
MODULE_11_DIVISOR = 11
MAX_DIGIT_VALUE = 10


def validate_cpf(cpf: str):
    cpf = ''.join(filter(str.isdigit, cpf))

    if len(cpf) != CPF_LENGTH or len(set(cpf)) == 1:
        raise ValidationError('CPF inválido.')

    sum_val = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digit_1 = (sum_val * 10) % 11
    if digit_1 == MAX_DIGIT_VALUE:
        digit_1 = 0

    if digit_1 != int(cpf[9]):
        raise ValidationError('CPF inválido.')

    sum_val = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digit_2 = (sum_val * 10) % 11
    if digit_2 == MAX_DIGIT_VALUE:
        digit_2 = 0

    if not digit_2 == int(cpf[10]):
        raise ValidationError('CPF inválido.')
    else:
        pass
