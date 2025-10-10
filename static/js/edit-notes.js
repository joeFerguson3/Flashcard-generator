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
    showLoading(document.body)
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
    // cancelLoading();
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
            const content = [...sub.querySelectorAll('.content')]
                .flatMap(span => span.innerText.split('\n').map(line => line.trim()))
                .filter(line => line.length > 0);

            data.push({
                main_title: mainTitle,
                sub_title: subTitle,
                content: content
            });
        });
    });

    console.log("extracted notes: ", data)
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

    showLoading(card)

    contentLines = ""
    for (const subCard of subCards) {

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


}

// Displays the enhanced note on the page
function displayEnhancedNote(enhancedText, card) {
    let html = "";
    let mainTitle = "";

    for (const [index, subCard] of enhancedText.entries()) {
        // If it's a new main title group
        if (subCard['main_title'] !== mainTitle) {
            if (mainTitle !== "") {
                // Close the previous card-nav if it exists
                html += `</div>`;
            }

            html += `
                <div class="card-nav note-group">
                    <div class="title note-group__header">
                        <h2 contenteditable="true">${subCard['main_title']}</h2>
                        <div class="note-card-btns">
                            <button onclick="enhanceNote(event)" contenteditable="false" class="sub-card-button edit btn-secondary btn">Enhance</button>
                        </div>
                    </div>
            `;

            mainTitle = subCard['main_title'];
        }

        // Build each sub-card
        html += `
            <div class="sub-card" id="sub_${subCard['main_title'].replace(/\s+/g, '_')}_${index}">
                <div class="sub-note-container">
                    <h3 contenteditable="true">${subCard['sub_title']}</h3>
                    <div class="sub-card-btn-container note-card-btns">
                        <button onclick="deleteNote(event)" contenteditable="false" class="sub-card-button delete btn btn-danger">Delete</button>
                    </div>
                </div>
                <div class="content note-content" contenteditable="true">
                    ${subCard['content'].map(line => `${line}<br>`).join('')}
                </div>
            </div>
        `;
    }

    // Close last opened note-group if it exists
    if (html !== "") {
        html += `</div>`;
    }

    cancelLoading();

    // Replace the existing card with new HTML
    card.outerHTML = html;
}

