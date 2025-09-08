
// Goes to next card in flash card set
function nextCard(title){
    let counter = document.getElementById("card_num_" + title);
    let counterNum = parseInt(counter.innerText, 10);

    let card_show = document.getElementById(title + String(counterNum + 1));
    // Checks next card exists
    if(card_show === null){
        return
    }
    let card_hide = document.getElementById(title + String(counterNum));

    counterNum += 1;
    counter.innerText = counterNum;

    card_hide.style.display = "none"
    card_show.style.display = "block"
}

// Goes to previous card in flash card set
function previousCard(title){
    let counter = document.getElementById("card_num_" + title);
    let counterNum = parseInt(counter.innerText, 10);

    let card_show = document.getElementById(title + String(counterNum - 1));
    // Checks next card exists
    if(card_show === null){
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
function next(currentId, skip=true) {
    // Hide the current element
    const current = document.getElementById(currentId);
    if (!current) return;

    // When question is skipped
    if (current.className == "question" && skip){
        const inputs = current.querySelectorAll("input, textarea");

        inputs.forEach(input => {
            const span = document.createElement("span");
            span.textContent = input.dataset.answer; // use input value as answer
            span.classList.add("incorrect-answer");

            input.replaceWith(span); // replace input with span
        });
    }

    const currentButton = document.getElementById("next-button" + currentId);
    currentButton.style.display = "none";

    // Find the next element
    const nextElement = current.nextElementSibling;
 
    if (nextElement) {
        nextElement.style.display = "grid";
    }

    // Scrolls page down
    nextElement.scrollIntoView({ behavior: "smooth", block: "end" });

    // Updates progress bar
    const bar = document.getElementById("progress-bar");
    let width = ( parseFloat(bar.style.width) || 0 ) + (100 / numElements()) * 1.3
    bar.style.width = width + "%"

}

// Gets the number of elements in the quiz
function numElements(){
    const totalCount = document.querySelectorAll('.question, .card-nav').length;
    return totalCount;
}

// Checks user answers
document.addEventListener("DOMContentLoaded", function() {
  let inputs = document.querySelectorAll(".blank-textbox, .answer-box");

  for (let i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("input", function() {
       let answer  = this.dataset.answer
      let typed = this.value;  // current text in the box

      let fuse = new Fuse([answer], { includeScore: true, threshold: 0.25 });
      let result = fuse.search(typed)
      // When correct answer
      if(result.length > 0 && result[0].score < 0.25 && typed.length >= Math.round(answer.length * 0.7)){
        let span = document.createElement("span");
        span.textContent = this.dataset.answer; 
        span.classList.add("correct-answer");

        this.parentNode.replaceChild(span, this);
        // Goes to next question
        if(span.closest(".question").querySelector("input, textarea") == null){
            next(span.closest(".question").id, false);
        }
      }
    });
  }
});
