document.addEventListener('DOMContentLoaded', function () {
    const nameField = document.querySelector('input[name="name"]');
    const nameDiv = document.getElementsByClassName('form-row field-name')
    if (nameDiv[0]) {
        nameDiv[0].children[0].children[0].children[1].textContent = name_mask(nameDiv[0].children[0].children[0].children[1].textContent)
    }
    if (nameField) {
        nameField.value = name_mask(nameField.value)
        nameField.addEventListener('input', function (event) {
            return event.target.value = name_mask(event.target.value)
        });
    }
});

function name_mask(v) {
    let value = v.replace(/[0-9!@#$%&*()_+={}\[\]:;"'<>,.?/\\|]/g, '');
    return value.split(' ').map((word, index) => {
        if (word.length > 1 || word.split('')[index] == word.split('')[0]) {
            return word.charAt(0).toUpperCase() + word.slice(1);
        }
        return word;
    }).join(' ');
}