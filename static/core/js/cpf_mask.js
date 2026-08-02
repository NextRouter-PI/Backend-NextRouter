document.addEventListener('DOMContentLoaded', function () {
    const cpfField = document.querySelector('input[name="cpf"]');
    const cpfDiv = document.getElementsByClassName('form-row field-cpf');

    if (cpfDiv[0] && cpfDiv[0].children[0]?.children[0]?.children[1]) {
        const textElement = cpfDiv[0].children[0].children[0].children[1];
        textElement.textContent = cpf_mask(textElement.textContent);
    }

    if (cpfField) {
        cpfField.value = cpf_mask(cpfField.value);
        cpfField.setAttribute('maxlength', '14');
        cpfField.addEventListener('input', function (event) {
            event.target.value = cpf_mask(event.target.value);
        });
    }
});

function cpf_mask(e) {
    if (!e) return '';

    let value = e.replace(/\D/g, '');

    if (value.length > 11) {
        value = value.slice(0, 11);
    }

    if (value.length > 0) {
        value = value.replace(/^(\d{3})(\d)/, '$1.$2');
        value = value.replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3');
        value = value.replace(/\.(\d{3})(\d)/, '.$1-$2');
    }

    return value;
}