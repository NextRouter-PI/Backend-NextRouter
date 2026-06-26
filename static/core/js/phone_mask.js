document.addEventListener('DOMContentLoaded', function () {
    const phoneField = document.querySelector('input[name="phone"], input[name="contact_phone"]');
    const phoneDiv = document.getElementsByClassName('form-row field-phone')
    if (phoneDiv[0]) {
        phoneDiv[0].children[0].children[0].children[1].textContent = phone_mask(phoneDiv[0].children[0].children[0].children[1].textContent)
    }
    if (phoneField) {
        phoneField.value = phone_mask(phoneField.value)
        phoneField.setAttribute('maxlength', '15');
        phoneField.addEventListener('input', function (event) {
            return event.target.value = phone_mask(event.target.value)
        });
    }
});

function phone_mask(v) {
    let value = v.replace(/\D/g, '');
    if (value.length > 11) value = value.slice(0, 14);

    if (value.length > 0) {
        value = value.replace(/^(\d{2})(\d)/g, "($1) $2");
        if (value.length > 9) {
            value = value.replace(/(\d{5})(\d)/, "$1-$2");
        } else {
            value = value.replace(/(\d{4})(\d)/, "$1-$2");
        }
    }
    return value;
}