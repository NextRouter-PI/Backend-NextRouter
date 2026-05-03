document.addEventListener('DOMContentLoaded', function () {
    const cnpjField = document.querySelector('input[name="cnpj"]');
    const cnpjDiv = document.getElementsByClassName('form-row field-cnpj')
    if (cnpjDiv[0]) {
        cnpjDiv[0].children[0].children[0].children[1].textContent = cnpj_mask(cnpjDiv[0].children[0].children[0].children[1].textContent)
    }
    if (cnpjField) {
        cnpjField.value = cnpj_mask(cnpjField.value)
        cnpjField.setAttribute('maxlength', '18');
        cnpjField.addEventListener('input', function (event) {
            return event.target.value = cnpj_mask(event.target.value)
        });
    }
});

function cnpj_mask(e) {
    let value = e.replace(/\D/g, '');

    if (value.length > 14) {
        value = value.slice(0, 14);
    }

    if (value.length > 0) {
        value = value.replace(/^(\d{2})(\d)/, "$1.$2");
        value = value.replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3");
        value = value.replace(/\.(\d{3})(\d)/, ".$1/$2");
        value = value.replace(/(\d{4})(\d)/, "$1-$2");
    }

    return value;
}