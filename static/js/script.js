
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
function next(currentId) {
    // Hide the current element
    const current = document.getElementById(currentId);
    if (!current) return;

    const currentButton = document.getElementById("next-button" + currentId);
    currentButton.style.display = "none";

    // Find the next element
    const nextElement = current.nextElementSibling;
 
    if (nextElement) {
        nextElement.style.display = "grid";
    }
}