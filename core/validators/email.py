from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _


def validate_email(value):
    validator = EmailValidator(message=_('%(value)s não é um e-mail válido.'))
    try:
        validator(value)
    except ValidationError:
        raise ValidationError(_('%(value)s não é um e-mail válido.'), params={'value': value}, code='invalid_email')
