
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
function quizSteps() {
    return Array.from(document.querySelectorAll('.quiz-step'));
}

document.addEventListener("DOMContentLoaded", () => {
    quizSteps().forEach((step, index) => {
        const isInitiallyActive = step.classList.contains('is-active');
        if (!isInitiallyActive) {
            step.hidden = true;
        } else if (index === 0) {
            step.hidden = false;
        }
    });
});

function next(currentId, skip = true) {
    const current = document.getElementById(currentId);
    if (!current) return;

    if (current.classList.contains("question") && skip) {
        const inputs = current.querySelectorAll("input[data-answer], textarea[data-answer]");
        inputs.forEach(input => {
            const span = document.createElement("span");
            span.textContent = input.dataset.answer;
            span.classList.add("incorrect-answer");
            span.classList.add("answer-reveal");
            input.replaceWith(span);
        });
    }

    if (current.classList.contains("question")) {
        current.dataset.completed = 'true';
        if (skip && current.dataset.result !== 'correct') {
            current.dataset.result = 'incorrect';
        }
    }

    const nextButton = current.querySelector('[data-role="next"]');
    if (nextButton) {
        nextButton.disabled = true;
        nextButton.setAttribute('aria-disabled', 'true');
        nextButton.classList.add('is-complete');
    }

    const steps = quizSteps();
    const currentIndex = steps.indexOf(current);
    const nextStep = steps[currentIndex + 1];

    if (nextStep) {
        nextStep.hidden = false;
        nextStep.classList.add('is-active');
        nextStep.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
        const computedScore = getScore();
        const normalizedScore = Number.isFinite(computedScore) ? Math.floor(computedScore * 100) / 100 : null;
        const finishButton = document.getElementById('finish-quiz-btn');
        if (finishButton) {
            finishButton.textContent = normalizedScore !== null ? `Finish quiz (${normalizedScore}%)` : 'Finish quiz';
            finishButton.style.display = 'inline-flex';
            finishButton.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        const scoreField = document.getElementById("final-score");
        if (scoreField) {
            scoreField.value = normalizedScore !== null ? normalizedScore : '';
        }
    }

    updateProgress(currentIndex + 1, steps.length);
}

function updateProgress(completedSteps, totalSteps) {
    const bar = document.getElementById("progress-bar");
    if (!bar || totalSteps === 0) return;
    const percent = Math.min(100, (completedSteps / totalSteps) * 100);
    bar.style.width = percent + "%";
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

                const questionEl = span.closest(".question");
                this.parentNode.replaceChild(span, this);
                // Goes to next question
                if (questionEl && questionEl.querySelector("input, textarea") == null) {
                    questionEl.dataset.result = 'correct';
                    questionEl.dataset.completed = 'true';
                    next(questionEl.id, false);
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
        const questionSection = button.closest(".question");
        if (questionSection) {
            questionSection.dataset.result = 'correct';
            questionSection.dataset.completed = 'true';
        }
        increaseScore()
    } else {
        button.classList.add("incorrect-answer");
        const questionSection = button.closest(".question");
        if (questionSection) {
            questionSection.dataset.result = 'incorrect';
            questionSection.dataset.completed = 'true';
        }
        const allButtons = questionSection ? questionSection.querySelectorAll("button") : [];

        allButtons.forEach(btn => {
            if (btn.innerText.trim() === answer.trim()) {
                btn.classList.add("corrected-answer");
            }
        });
    }

    const questionContainer = button.closest(".question");
    next(questionContainer.id, false);
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

    const questionEl = form.closest(".question");
    if (questionEl) {
        questionEl.dataset.result = correct ? 'correct' : 'incorrect';
        questionEl.dataset.completed = 'true';
    }
    if (correct) increaseScore()
    next(questionEl.id, false);
}

let score = 0
function increaseScore() {
    q_num = document.querySelectorAll(".question").length
    score = score + 100 / q_num
    console.log(score)
}

// Displays loading screen
function showLoading(element) {
    let loading;
    if (typeof element === 'string') {
        loading = document.querySelector(element)
    } else {
        loading = element
    }

    loaderHTML = `<div id="overlay" class="overlay">
    <div class="spinner"></div>
    <p>Loading...</p>
    </div>`

    console.log("laoding: ", loading)
    loading.style.position = 'relative';
    loading.insertAdjacentHTML('beforeend', loaderHTML);
    console.log("laoding: ", loading)
}

function cancelLoading(){
    document.querySelectorAll('.overlay').forEach(e => e.remove());
}

function getScore() {
    const questions = document.querySelectorAll('.question');
    if (!questions.length) return 0;
    let correctCount = 0;
    questions.forEach(question => {
        if (question.dataset.result === 'correct') {
            correctCount += 1;
        }
    });
    return (correctCount / questions.length) * 100;
}
