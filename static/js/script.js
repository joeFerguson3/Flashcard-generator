
// Goes to next card in flash card set
function nextCard(title) {
    let counter = document.getElementById("card_num_" + title);
    let counterNum = parseInt(counter.innerText, 10);

    let card_show = document.getElementById(title + String(counterNum + 1));
    // Checks next card exists
    if (card_show === null) {
        return
    }
    let card_hide = document.getElementById(title + String(counterNum));

    counterNum += 1;
    counter.innerText = counterNum;

    card_hide.style.display = "none"
    card_show.style.display = "block"
}

// Goes to previous card in flash card set
function previousCard(title) {
    let counter = document.getElementById("card_num_" + title);
    let counterNum = parseInt(counter.innerText, 10);

    let card_show = document.getElementById(title + String(counterNum - 1));
    // Checks next card exists
    if (card_show === null) {
        return
    }
    let card_hide = document.getElementById(title + String(counterNum));

    counterNum -= 1;
    counter.innerText = counterNum;

    card_hide.style.display = "none"
    card_show.style.display = "block"
}

// // Goes to next question or notes
// function next(button, main_title){
//     document.getElementById(main_title).style.display = "grid"
//         console.log(button)
//     document.getElementById(button).style.display = "none"

// }

// Goes to next question or notes
function next(currentId, skip = true) {
    // Hide the current element
    const current = document.getElementById(currentId);
    if (!current) return;

    // When question is skipped
    if (current.className == "question" && skip) {
        const inputs = current.querySelectorAll("input, textarea");

        inputs.forEach(input => {
            const span = document.createElement("span");
            span.textContent = input.dataset.answer; // user input value as answer
            span.classList.add("incorrect-answer");

            input.replaceWith(span); // replace input with span
        });
    }

    const currentButton = document.getElementById("next-button" + currentId);
    currentButton.style.display = "none";

    // Find the next element
    let nextElement = current.nextElementSibling;
    if (nextElement.nextElementSibling.nextElementSibling.classList.contains("card-nav") || nextElement.nextElementSibling.nextElementSibling.classList.contains("question")) {
        nextElement.style.display = "grid";
    } else {
        nextElement = document.getElementById("finish-quiz-btn")
        nextElement.style.display = "block";
    }

    // Scrolls page down
    nextElement.scrollIntoView({ behavior: "smooth", block: "end" });

    // Updates progress bar
    const bar = document.getElementById("progress-bar");
    let width = (parseFloat(bar.style.width) || 0) + (80 / numElements())
    bar.style.width = width + "%"

}

// Gets the number of elements in the quiz
function numElements() {
    const totalCount = document.querySelectorAll('.question, .card-nav').length - 1;
    return totalCount;
}

// Checks user typed answers
document.addEventListener("DOMContentLoaded", function () {
    let inputs = document.querySelectorAll(".blank-textbox, .answer-box");

    for (let i = 0; i < inputs.length; i++) {
        inputs[i].addEventListener("input", function () {
            let answer = this.dataset.answer
            let typed = this.value;  // current text in the box

            let fuse = new Fuse([answer], { includeScore: true, threshold: 0.25 });
            let result = fuse.search(typed)
            // When correct answer
            if (result.length > 0 && result[0].score < 0.25 && typed.length >= Math.round(answer.length * 0.7)) {
                let span = document.createElement("span");
                span.textContent = this.dataset.answer;
                span.classList.add("correct-answer");

                this.parentNode.replaceChild(span, this);
                // Goes to next question
                if (span.closest(".question").querySelector("input, textarea") == null) {
                    next(span.closest(".question").id, false);
                    increaseScore()
                }
            }
        });
    }
});

// Checks true false answers
function checkAnswerTF(event, answer) {
    event.preventDefault();

    const button = event.target
    const userAnswer = button.value;
    if (userAnswer.toLowerCase() == answer.toLowerCase()) {
        button.classList.add("correct-answer");
        increaseScore()
    } else {
        button.classList.add("incorrect-answer");
        question = button.closest(".true-false-form")
        allButtons = question.querySelectorAll("button");
        console.log(allButtons)
        allButtons.forEach(btn => {
            if (btn.innerText.trim() === answer.trim()) {
                btn.classList.add("correct-answer");
            }
        });
    }

    next(button.closest(".question").id, false);
}


// Responsible for allowing dragging quiz ordering questions
document.querySelectorAll('.draggable').forEach(item => {
    item.setAttribute('draggable', true);
    item.addEventListener('dragstart', dragStart);
    item.addEventListener('dragover', dragOver);
    item.addEventListener('drop', drop);
    item.addEventListener('dragleave', dragLeave);
});

let dragSrcEl = null;
let prev = null;

function dragStart(e) {
    dragSrcEl = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function dragOver(e) {
    e.preventDefault(); // allow dropping
    if (prev) {
        prev.style.outline = "0px";
    }
    prev = this;
    this.style.outline = "3px solid black";
}

function dragLeave(e) {
    this.style.outline = "0px"; // remove highlight if you drag away
}

function drop(e) {
    e.stopPropagation();
    if (dragSrcEl !== this) {
        const tmp = dragSrcEl.innerHTML;
        dragSrcEl.innerHTML = this.innerHTML;
        this.innerHTML = tmp;
    }
    this.style.outline = "0px"; // clear outline on drop
}

// Checks ordering question
function checkOrdering(e) {
    e.preventDefault();

    const form = e.target
    const items = form.querySelectorAll("li");

    const user_answer = Array.from(items).map(li => li.innerText.trim());
    const answer = JSON.parse(form.dataset.answer)
    correct = true
    for (let i = 0; i < answer.length; i++) {

        if (user_answer[i] == answer[i].trim()) {
            items[i].classList.add("correct-answer");
            items[i].value = answer.indexOf(user_answer[i]) + 1
        } else {
            items[i].classList.add("incorrect-answer");
            items[i].value = answer.indexOf(user_answer[i]) + 1
            correct = false
        }
    }

    if (correct) increaseScore()
    next(form.closest(".question").id, false);
}

let score = 0
function increaseScore() {
    q_num = document.querySelectorAll(".question").length
    score = score + 100 / q_num
    console.log(score)
}

// Displays loading screen
function showLoading(element) {
    let loading = document.querySelector(element)

    loaderHTML = `<div id="overlay" class="overlay">
    <div class="spinner"></div>
    <p>Loading...</p>
    </div>`

    loading.style.position = 'relative';
    loading.insertAdjacentHTML('beforeend', loaderHTML);
}