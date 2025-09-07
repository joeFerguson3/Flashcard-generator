
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