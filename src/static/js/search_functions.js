document.addEventListener("DOMContentLoaded", function () {
  const translateButton = document.getElementById("translate-button");
  const naturalLanguageQueryInput = document.querySelector("input[name='natural_language_query']");
  const booleanQueryInput = document.querySelector("input[name='query']");

  translateButton.addEventListener("click", async function (event) {
    event.preventDefault();
    if (!naturalLanguageQueryInput.value.trim()) {
      alert("Please enter a natural language query to translate.");
    return;
    }

    translateButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Translating...`;
    translateButton.disabled = true;

    try {
    const response = await axios.get(`/api/nl-to-bool-query/${encodeURIComponent(naturalLanguageQueryInput.value)}/`);
    if (response.status === 200 && response.data.query) {
        booleanQueryInput.value = response.data.query;
    } else {
        alert("Error translating the natural language query.");
    }
    } catch (error) {
    alert("Failed to connect to the translation service.");
    } finally {
      translateButton.innerHTML = "Translate";
      translateButton.disabled = false;
    }
  });
});

document.addEventListener("DOMContentLoaded", function() {
  // Select necessary DOM elements
  const evaluateButton = document.querySelector("button[name='submit'][value='evaluate']");
  const createProjectButton = document.querySelector("button[name='submit'][value='search']");
  const selectedIndicesField = document.querySelector("#selectedIndicesField");
  const radioButtons = document.querySelectorAll(".index-radio");

  /**
   * Updates the hidden field with the selected radio value.
   */
  function updateSelectedIndicesField() {
    const selectedRadio = Array.from(radioButtons).find(radio => radio.checked);
    if (selectedRadio) {
      selectedIndicesField.value = selectedRadio.value;
    }
  }

  // Attach change event listeners to radio buttons to update the hidden field dynamically
  radioButtons.forEach(radio => {
    radio.addEventListener("change", updateSelectedIndicesField);
  });

  // Attach event listeners for Evaluate and Create Project buttons to update selected indices
  evaluateButton.addEventListener("click", function(event) {
    updateSelectedIndicesField();  // Update hidden field with selected index
  });

  createProjectButton.addEventListener("click", function(event) {
    updateSelectedIndicesField();  // Update hidden field with selected index
  });

  // Initial setup for updating the hidden field when page loads
  updateSelectedIndicesField();

  // Original JavaScript functionality for modal and other UI components
  const projectNameInput = document.querySelector("input[name='name']");
  const uploadFilesButton = document.querySelector("button[data-bs-target='#staticBackdrop']");
  const removeFilesButton = document.querySelector("button[value='remove_uploaded']");
  const modalCancelButton = document.querySelector(".modal-footer button[value='cancel']");
  const modalCloseButton = document.querySelector(".modal-header button[value='cancel']");
  const modalContinueButton = document.querySelector("button[value='continue']");

  function makeSpinnerHTML(message = "") {
    return (`<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${message}`);
  };

  function handleButtonClick(clickedButton, otherButton, spinnerHtml, callback) {
  if (projectNameInput.value) {

    clickedButton.style.pointerEvents = "none";
    clickedButton.classList.add("disabled");
    clickedButton.innerHTML = spinnerHtml;

    otherButton.style.pointerEvents = "none";
    otherButton.classList.add("disabled");
    otherButton.parentElement.style.cursor = "not-allowed";

    uploadFilesButton.style.pointerEvents = "none";
    uploadFilesButton.classList.add("disabled");
    removeFilesButton.style.pointerEvents = "none";
    removeFilesButton.classList.add("disabled");

    if (typeof callback === 'function') {
    callback();
    }
  }
  }

  // Functions to handle button clicks
  function handleEvaluateButtonClick() {
    const evaluateSpinner = makeSpinnerHTML("Evaluating...");
    handleButtonClick(evaluateButton, createProjectButton, evaluateSpinner);
  }

  function handleCreateProjectButtonClick() {
    const createProjectSpinner = makeSpinnerHTML("Creating...");
    handleButtonClick(createProjectButton, evaluateButton, createProjectSpinner);
  }

  function handleContinueButtonClick() {
    const continueSpinner = makeSpinnerHTML("Starting...");
    handleButtonClick(modalContinueButton, modalCancelButton, continueSpinner, function() {
      modalCloseButton.classList.add("disabled");
      modalCloseButton.style.pointerEvents = "none";
  });
  }

  // Attach event listeners to the buttons
  evaluateButton.addEventListener('click', handleEvaluateButtonClick);
  createProjectButton.addEventListener('click', handleCreateProjectButtonClick);

  if (modalContinueButton) {
    modalContinueButton.addEventListener('click', handleContinueButtonClick);
  }
});
