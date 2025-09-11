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
    if (isEdited) {
        const notes = [...document.querySelectorAll('.sub-card')].map(card => card.innerText.trim());

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

    } else {
        fetch('/generate-quiz', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
              credentials: 'include', 
            body: JSON.stringify({ notes: getNotes() })
        })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                }
            })
    }

};

// Extracts notes from page as JSON
function getNotes() {
    const cards = document.querySelectorAll('.card-nav');
    const data = [];

    cards.forEach(card => {
        const mainTitle = card.querySelector('h2').innerText.trim();

        const subCards = card.querySelectorAll('.sub-card');
        subCards.forEach(sub => {
            const subTitle = sub.querySelector('h3').innerText.trim();

            // Get all <span> inside this sub-card as content lines
            const content = [...sub.querySelectorAll('span')]
                .map(span => span.innerText.trim())
                .filter(line => line.length > 0); // skip empty lines

            data.push({
                main_title: mainTitle,
                sub_title: subTitle,
                content: content
            });
        });
    });
    return data
}