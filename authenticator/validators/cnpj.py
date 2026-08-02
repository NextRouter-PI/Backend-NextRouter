from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

CNPJ_LENGTH = 14

# TODO - Revisar código

def validate_cnpj(value):
    cnpj = ''.join(filter(str.isdigit, str(value)))

    if len(cnpj) != CNPJ_LENGTH:
        raise ValidationError(_('O CNPJ deve conter exatamente 14 dígitos numéricos.'), code='invalid_cnpj_format')

    if cnpj == cnpj[0] * CNPJ_LENGTH:
        raise ValidationError(_('%(value)s não é um CNPJ válido.'), params={'value': value}, code='invalid_cnpj')

    def calcular_digito(cnpj, pesos):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(len(pesos)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    digito_1 = calcular_digito(cnpj, pesos_1)
    digito_2 = calcular_digito(cnpj, pesos_2)

    if int(cnpj[12]) != digito_1 or int(cnpj[13]) != digito_2:
        raise ValidationError(_('%(value)s não é um CNPJ válido.'), params={'value': value}, code='invalid_cnpj')
