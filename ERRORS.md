django-nullable-model-string-field: Avoid using `null=True` on string-based fields such as `CharField` 

No padrão atual do Django é recomendado que campos de texto nas models (EmailField, CharField, TextField...) não usar null=True. Isso evita que em consultas filtradas no banco, precise passar tanto argumento None (valor nulo) quanto "" (string vazia).

mutable-class-default: Mutable default value for class attribute

Esse erro indica que uma variável é mutável por padrão, mas que deve ser trocada para uma tupla.

Consider `(*self.readonly_fields, 'user', 'cnpj')` instead of concatenation

help: Replace with `(*self.readonly_fields, 'user', 'cnpj')`Ruffcollection-literal-concatenation