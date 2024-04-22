const checkedboxes = document.querySelectorAll("input[name=check_row]");
let counter = document.querySelector(".article-counter");
let counterBottom = document.querySelector(".article-counter-bottom")
checkedboxes.forEach(checkbox => checkbox.addEventListener("click", (e) =>{
  
  if(e.target.checked == true){
    selectedArticles = parseInt(counter.textContent);
    counter.textContent = selectedArticles + 1;
    counterBottom.textContent =selectedArticles + 1;
  }
  else {
    counter.textContent -= 1;
    counterBottom.textContent -= 1;
  }

}))
