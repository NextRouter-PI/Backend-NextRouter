from django.core.exceptions import ValidationError


def related_values(instance, field, *columns):
    """Consulta segura para clean; não substitui revalidação transacional."""
    relation = instance._meta.get_field(field)
    model = relation.remote_field.model
    try:
        pk = model._meta.pk.to_python(getattr(instance, relation.attname))
    except ValidationError:
        return None
    return model.objects.filter(pk=pk).values(*columns).first() if pk is not None else None


def same_company(errors, field, related, company_id):
    if related and company_id is not None and related['company_id'] != company_id:
        errors[field] = 'O recurso deve pertencer à mesma empresa.'
