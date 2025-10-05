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
    showLoading("body")
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
        console.log("yes")
        const title = document.getElementById('notes-title')
        const subject = document.getElementById('notes-subject')

        fetch('/generate-quiz', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ subject: subject.innerText, title: title.innerText, notes: getNotes() })
        })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                }
            })
    }
    removeLoading();
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

function deleteNote(event) {
    const button = event.target;
    const subCard = button.closest('.sub-card');

    if(button.closest('.card-nav').querySelectorAll('.sub-card').length === 1){
        button.closest('.card-nav').remove();
    }
        subCard.remove();
}

function enhanceNote(event) {
    const button = event.target;
    const card = button.closest('.card-nav');

    const subCards = card.querySelectorAll('.sub-card');
    if (subCards.length === 0) return; // No sub-cards to enhance

    contentLines = ""
    for (const subCard of subCards) {
        showLoading(subCard)
        const subTitle = subCard.querySelector('h3').innerText.trim();
        const contentSpans = subCard.querySelector('.content').innerText;
        contentLines += "##" + subTitle + "\n" + contentSpans + "\n\n";
    }

    console.log(contentLines)
    fetch('/enhance-note', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ note: contentLines })
    })
        .then(response => response.json())
        .then(data => {
            displayEnhancedNote(data.note, card);
        })

    cancelLoading();
}

// Displays the enhanced note on the page
function displayEnhancedNote(enhancedText, card) {
    html = ""
    mainTitle = ""
    for (subCard of enhancedText) {
        if (subCard['main_title'] != mainTitle) {
            html +=  `<div class="card-nav">
                <div class="title">
                    <h2 contenteditable="true">${subCard['main_title']}</h2>
                    <button onclick="enhanceNote(event)" contenteditable="false"
                        class="sub-card-button edit">enhance</button>
                </div>`
            mainTitle = subCard['main_title']
        }

        html += `<div class="sub-card">
                            <div class="sub-note-container">
                                <h3 contenteditable="true" >${subCard['sub_title']}</h3>
                                <div class="sub-card-btn-container">
                                    <button onclick="deleteNote(event)" contenteditable="false"
                                        class="sub-card-button delete">delete</button>
                                </div>
                            </div>`
        html += `<div class="content" contenteditable="true">`
        for (line of subCard['content']) {
            html += `${line}<br>`
        }
        html += `</div></div></div>`
    }

    card.outerHTML = html;
}
