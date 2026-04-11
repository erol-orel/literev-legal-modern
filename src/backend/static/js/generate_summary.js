/*
 * This script is designed for integration with the previousgraph.html template.
 * It is advisable to perform DOM manipulation within the ready function to ensure
 * that the HTML content is fully loaded and parsed before the script interacts
 * with DOM elements.
 *
 * The main function serves as the entry point, allowing the inclusion of various
 * routines for execution.
 */


/**
 * The main function that is executed when the DOM content is fully loaded.
 * Any code behavior can be encapsuated in a function and called here.
 */
function main() {
    document.addEventListener("DOMContentLoaded", function () {
        openaiFallback();
    });
}


/**********************************
* Helper Functions
***********************************/

/**
 * Generates HTML code for a spinner with an optional message.
 *
 * @param {string} [message=""] - An optional message to display alongside the spinner.
 * @returns {string} The HTML code for a spinner element with the specified message.
 */
function makeSpinnerHTML(message = "") {
    return (
        `<span class="spinner-border spinner-border-sm"
        role="status" aria-hidden="true"></span> ${message}`
    );
};


/*****************************************************
* Main Routine Functions
*
* Those functions encapsulates specific behavior and/or
* functionalities and are called inside the main function
*********************************************************/


/**
 * Sets up event listeners for OpenAI summary generation buttons.
 * Ensures that the HTML content is loaded before interacting with DOM elements.
 * Uses ajax to send a POST request to the OpenAI API.
 * This routine is executed in the main function
 */
async function openaiFallback() {
    // select elements that will be used
    const generateSummaryButtons = document.querySelectorAll(".generate-summary-button");

    if (generateSummaryButtons) {
        // check if there are buttons rendered
        generateSummaryButtons.forEach(button => {
            // add click event
            button.addEventListener("click", handleSummaryButtonClick)
        })
    }

    async function handleSummaryButtonClick(event) {
        // get the clicked button by the event
        const clickedButton = event.target;

        // cache the button innerHTML for later
        const buttonDefaultInnerHTML = clickedButton.innerHTML;

        // get the url and csrf token
        const generateSummaryUrl = clickedButton.getAttribute("data-generate-summary-url");
        const csrfToken = clickedButton.getAttribute("data-csrf-token");

        // disable the button and add spinner loading effect
        clickedButton.style.pointerEvents = "none";
        clickedButton.classList.add("disabled");
        clickedButton.innerHTML = makeSpinnerHTML("Generating summary...");

        try {
            // call the generate summary view
            const response = await fetch(generateSummaryUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken, // pass csrf token
                    "Content-Type": "application/json",
                }
            });

            if (!response.ok) {
                // catch the error if response status is not ok
                throw response;
            } else {
                // handle success response
                const data = await response.json();

                // get the closes table td element
                const tdElement = clickedButton.closest("td");
                // swap the td content by the new generated summary
                tdElement.innerHTML = data.content;
            }
        } catch (error) {
            // handle error cases

            // re-enable the button
            clickedButton.style.pointerEvents = "auto";
            clickedButton.classList.remove("disabled");
            // swap the original button state back
            clickedButton.innerHTML = buttonDefaultInnerHTML;

            if (error.status == 503) {
                // handle the case where the service is still unavailable
                return error.json().then(errorData => {
                    const alertElement = clickedButton.closest("td").querySelector(".alert");
                    // show the error message to the user
                    alertElement.classList.remove("alert-light");
                    alertElement.classList.add("alert-warning");
                    alertElement.textContent = errorData.content;
                })
            }
        }
    }
};

// Execute main function
main();
