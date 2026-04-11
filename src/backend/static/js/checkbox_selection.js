// Code for checking all checkboxes
let initialCheckedYes = 0;

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

  let actualCheckedYes = countYesChecked();

  checkboxesYes.forEach((checkbox) => {
    checkbox.checked = true;
  })
  checkboxesNo.forEach((checkbox) => {
    checkbox.checked = false;
  })
  checkboxesMaybe.forEach((checkbox) => {
    checkbox.checked = false;
  })

  let new_total_checked = countYesChecked();

  let counter = document.querySelector(".article-counter");
  let counterBottom = document.querySelector(".article-counter-bottom");
  let previousValue = parseInt(counter.textContent);
  counter.textContent = previousValue - actualCheckedYes + new_total_checked;
  counterBottom.textContent = previousValue - actualCheckedYes + new_total_checked;
  initialCheckedYes = countYesChecked();
}


function all2Maybe() {
  const checkboxesYes = document.getElementsByName("yes_row");
  const checkboxesNo = document.getElementsByName("no_row");
  const checkboxesMaybe = document.getElementsByName("maybe_row");

  let actualCheckedYes = countYesChecked();

  checkboxesYes.forEach((checkbox) => {
    checkbox.checked = false;
  })
  checkboxesNo.forEach((checkbox) => {
    checkbox.checked = false;
  })
  checkboxesMaybe.forEach((checkbox) => {
    checkbox.checked = true;
  })

  let new_total_checked = countYesChecked();

  let counter = document.querySelector(".article-counter");
  let counterBottom = document.querySelector(".article-counter-bottom");
  let previousValue = parseInt(counter.textContent);
  counter.textContent = previousValue - actualCheckedYes + new_total_checked;
  counterBottom.textContent = previousValue - actualCheckedYes + new_total_checked;

  initialCheckedYes = countYesChecked();
}

all2YesButtons = document.querySelectorAll(".all-yes-button");

all2YesButtons.forEach((button) => {
  button.addEventListener("click", all2Yes)
})

all2MaybeButtons = document.querySelectorAll(".all-maybe-button");

all2MaybeButtons.forEach((button) => {
  button.addEventListener("click", all2Maybe)
})


// To handle unique selection in 'yes', 'maybe', 'no' options
initialCheckedYes = countYesChecked();

const checkInputs = document.querySelectorAll(".form-check-input");
checkInputs.forEach((checkbox) => {
  checkbox.addEventListener("click", (e) => {

    targetCodeId = e.target.getAttribute('id');
    // get child
    const parent = e.target.parentElement.parentElement
    isTargetChecked = e.target.checked;

    const childsElements = parent.querySelectorAll(".form-check-input")
    childsElements.forEach((checkbox) => {

      if (isTargetChecked) {
        if (targetCodeId != checkbox.getAttribute('id')) {
          checkbox.checked = false;
        }
      }
      else {
        if (targetCodeId == checkbox.getAttribute('id')) {
          checkbox.checked = true;
        }
      }
    })
    let new_total_checked = countYesChecked();

    let counter = document.querySelector(".article-counter");
    let counterBottom = document.querySelector(".article-counter-bottom");
    let previousValue = parseInt(counter.textContent);
    counter.textContent = previousValue - initialCheckedYes + new_total_checked;
    counterBottom.textContent = previousValue - initialCheckedYes + new_total_checked;

    // storing the value of actual checked docs
    initialCheckedYes = new_total_checked
  })
})
