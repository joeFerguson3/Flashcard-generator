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
    if(isEdited){
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
        window.location.href = response.url;
    }
    });

    }else{
    //     fetch('/generate-quiz', {
    //     method: 'POST',
    //     headers: {
    //         'Content-Type': 'application/json'
    //     },
    //     body: JSON.stringify({ notes: notes })
    // })
    }

};
