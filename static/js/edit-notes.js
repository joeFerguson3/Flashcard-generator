/** Detects if note content is edited */
const editableSections = document.querySelectorAll('.sub-card');
const button = document.getElementById('generate-button');

// Flag to check if any section is edited
let isEdited = false;

editableSections.forEach(section => {
    section.addEventListener('input', () => {
        if (!isEdited) {
            isEdited = true;
            button.textContent = 'Regenerate Notes';
        }
    });
});

function generateQuiz() {
    const notes = [...document.querySelectorAll('.sub-card')].map(card => card.innerText.trim());
    console.log(notes)

    fetch('/regenerate-notes', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ notes: notes })
    })

       .then(response => {
    if (response.redirected) {
        // If Flask sent a redirect, follow it manually
        window.location.href = response.url;
    }
    });

};
