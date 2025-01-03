// Code for checking all checkboxes

function countYesChecked() {
  const checkboxesYes = document.getElementsByName("yes_row");
  let counter = 0;
  checkboxesYes.forEach((checkbox) => {
    if (checkbox.checked == true) {
      counter = counter + 1
    }
  })

  return counter
}

function all2Yes() {
  const checkboxesYes = document.getElementsByName("yes_row");
  const checkboxesNo = document.getElementsByName("no_row");
  const checkboxesMaybe = document.getElementsByName("maybe_row");

  actualCheckedYes = countYesChecked();

  checkboxesYes.forEach((checkbox) =>{
    checkbox.checked = true;
  })
  checkboxesNo.forEach((checkbox) =>{
    checkbox.checked = false;
  })
  checkboxesMaybe.forEach((checkbox) =>{
    checkbox.checked = false;
  })

  new_total_checked = countYesChecked();

  let counter = document.querySelector(".article-counter");
  let counterBottom = document.querySelector(".article-counter-bottom");
  let previousValue = parseInt(counter.textContent);
  counter.textContent = previousValue - actualCheckedYes + new_total_checked;
  counterBottom.textContent = previousValue - actualCheckedYes + new_total_checked;
}

function all2Maybe() {
  const checkboxesYes = document.getElementsByName("yes_row");
  const checkboxesNo = document.getElementsByName("no_row");
  const checkboxesMaybe = document.getElementsByName("maybe_row");

  actualCheckedYes = countYesChecked();

  checkboxesYes.forEach((checkbox) =>{
    checkbox.checked = false;
  })
  checkboxesNo.forEach((checkbox) =>{
    checkbox.checked = false;
  })
  checkboxesMaybe.forEach((checkbox) =>{
    checkbox.checked = true;
  })

  new_total_checked = countYesChecked();

  let counter = document.querySelector(".article-counter");
  let counterBottom = document.querySelector(".article-counter-bottom");
  let previousValue = parseInt(counter.textContent);
  counter.textContent = previousValue - actualCheckedYes + new_total_checked;
  counterBottom.textContent = previousValue - actualCheckedYes + new_total_checked;
}

all2YesButtons = document.querySelectorAll(".all-yes-button");

all2YesButtons.forEach((button) => {
  button.addEventListener("click", all2Yes)
})

all2MaybeButtons = document.querySelectorAll(".all-maybe-button");

all2MaybeButtons.forEach((button) => {
  button.addEventListener("click", all2Maybe)
})
