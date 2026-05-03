document.addEventListener('DOMContentLoaded', function () {
    const cepField = document.querySelector('input[name="cep"], input[name="commom_address"]');
    const cepDiv = document.querySelector('.field-cep, .field-commom_address');
    if (cepDiv[0]) {
        cepDiv[0].children[0].children[0].children[1].textContent = cep_mask(cepDiv[0].children[0].children[0].children[1].textContent)
    }
    if (cepField) {
        cepField.value = cep_mask(cepField.value)
        cepField.setAttribute('maxlength', '9');
        cepField.addEventListener('input', function (event) {
            return event.target.value = cep_mask(event.target.value)
        });
    }
});

function cep_mask(v) {
    let value = v.replace(/\D/g, '');
    if (value.length > 8) value = value.slice(0, 8);

    if (value.length > 5) {
        value = value.replace(/^(\d{5})(\d)/, "$1-$2");
    }
    return value;
}