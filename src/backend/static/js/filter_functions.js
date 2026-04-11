const topicSelectorContainer = document.querySelector("#topic-selector-container");
const valueSelectorContainer = document.querySelector("#value-selector-container");
const yearSelectorContainer = document.querySelector("#year-selector-container");
const normSelectorContainer = document.querySelector("#norm-selector-container");
const descriptorSelectorContainer = document.querySelector("#descriptor-selector-container");
const chamberSelectorContainer = document.querySelector("#chamber-selector-container");
const nodecisionSelectorContainer = document.querySelector("#nodecision-selector-container");
const resultSelectorContainer = document.querySelector("#result-selector-container");
const typeFilter = document.querySelector("#type-filter");

function checkKeySelector() {
  if (typeFilter.value == "Topic") {
    topicSelectorContainer.hidden = false;
    valueSelectorContainer.hidden = true;
    yearSelectorContainer.hidden = true;
    normSelectorContainer.hidden = true;
    descriptorSelectorContainer.hidden = true;
    chamberSelectorContainer.hidden = true;
    nodecisionSelectorContainer.hidden = true;
    resultSelectorContainer.hidden = true;
  }

  else if (typeFilter.value == "Norm") {
    topicSelectorContainer.hidden = true;
    valueSelectorContainer.hidden = true;
    yearSelectorContainer.hidden = true;
    normSelectorContainer.hidden = false;
    descriptorSelectorContainer.hidden = true;
    chamberSelectorContainer.hidden = true;
    nodecisionSelectorContainer.hidden = true;
    resultSelectorContainer.hidden = true;
  }

  else if (typeFilter.value == "No_decis") {
    topicSelectorContainer.hidden = true;
    valueSelectorContainer.hidden = true;
    yearSelectorContainer.hidden = true;
    normSelectorContainer.hidden = true;
    descriptorSelectorContainer.hidden = true;
    chamberSelectorContainer.hidden = true;
    nodecisionSelectorContainer.hidden = false;
    resultSelectorContainer.hidden = true;
  }

  else if (typeFilter.value == "Result") {
    topicSelectorContainer.hidden = true;
    valueSelectorContainer.hidden = true;
    yearSelectorContainer.hidden = true;
    normSelectorContainer.hidden = true;
    descriptorSelectorContainer.hidden = true;
    chamberSelectorContainer.hidden = true;
    nodecisionSelectorContainer.hidden = true;
    resultSelectorContainer.hidden = false;
  }

  else if (typeFilter.value == "year_range") {
    topicSelectorContainer.hidden = true;
    valueSelectorContainer.hidden = true;
    yearSelectorContainer.hidden = false;
    normSelectorContainer.hidden = true;
    descriptorSelectorContainer.hidden = true;
    chamberSelectorContainer.hidden = true;
    nodecisionSelectorContainer.hidden = true;
    resultSelectorContainer.hidden = true;
  }

  else if (typeFilter.value == "descriptors") {
    topicSelectorContainer.hidden = true;
    valueSelectorContainer.hidden = true;
    yearSelectorContainer.hidden = true;
    normSelectorContainer.hidden = true;
    descriptorSelectorContainer.hidden = false;
    chamberSelectorContainer.hidden = true;
    nodecisionSelectorContainer.hidden = true;
    resultSelectorContainer.hidden = true;
  }

  else if (typeFilter.value == "chamber") {
    topicSelectorContainer.hidden = true;
    valueSelectorContainer.hidden = true;
    yearSelectorContainer.hidden = true;
    normSelectorContainer.hidden = true;
    descriptorSelectorContainer.hidden = true;
    chamberSelectorContainer.hidden = false;
    nodecisionSelectorContainer.hidden = true;
    resultSelectorContainer.hidden = true;
  }


  else {
    topicSelectorContainer.hidden = true;
    valueSelectorContainer.hidden = false;
    yearSelectorContainer.hidden = true;
    normSelectorContainer.hidden = true;
    descriptorSelectorContainer.hidden = true;
    chamberSelectorContainer.hidden = true;
    nodecisionSelectorContainer.hidden = true;
    resultSelectorContainer.hidden = true;
  }
}

typeFilter.addEventListener("change", () => {
  checkKeySelector();
})

checkKeySelector();

// input factory
const inputFactory = (filterIdx) => {
  filterInput = document.createElement("input");
  filterInput.setAttribute("name", `filter-union-${filterIdx}`);
  filterInput.setAttribute("value", "");
  filterInput.hidden = true;

  return { filterInput }
}

// input exclude factory
const inputExcludeFactory = () => {
  filterInput = document.createElement("input");
  filterInput.setAttribute("name", `filter-exclude`);
  filterInput.setAttribute("value", "");
  filterInput.hidden = true;

  return { filterInput }
}

//create an input data object
const inputData = (() => {
  const container = document.querySelector("#input-json");
  const update = () => {

    while (container.firstChild) {
      container.removeChild(container.lastChild);
    }

    const n = unionFilterList.length;

    for (let i = 0; i < n; i++) {
      let inputList = unionFilterList[i].filterList;
      let filterJson = {};
      for (let tuple of inputList) {
        if (!(tuple[0] in filterJson)) {
          filterJson[tuple[0]] = [];
        }
        filterJson[tuple[0]].push(tuple[1]);
      }

      let filterValue = JSON.stringify(filterJson);
      let newFilterData = inputFactory(i);
      newFilterData.filterInput.setAttribute("value", filterValue);
      container.appendChild(newFilterData.filterInput);
    }

    let filterExcludeList = filterExclude.filterList;
    let filterExcludeJson = {};
    for (let tuple of filterExcludeList) {
      if (!(tuple[0] in filterExcludeJson)) {
        filterExcludeJson[tuple[0]] = [];
      }
      filterExcludeJson[tuple[0]].push(tuple[1]);
    }
    let filterExcludeValue = JSON.stringify(filterExcludeJson);
    let newFilterExcludeData = inputExcludeFactory();
    newFilterExcludeData.filterInput.setAttribute("value", filterExcludeValue);
    container.appendChild(newFilterExcludeData.filterInput);

  };

  const show = () => {
    let inputs = document.querySelectorAll("input[name^='filter-union']");
    for (let inp of inputs) {
      console.log(inp.name);
      console.log(inp.value);
    }

    let inputsExclude = document.querySelectorAll("input[name^='filter-exclude']");
    for (let inp of inputsExclude) {
      console.log(inp.name);
      console.log(inp.value);
    }
  };

  return { update, show }
})();


// AND tag factory
const andTag = () => {
  const divContainer = document.createElement("div");
  divContainer.classList.add("fs-5", "mt-2");
  const tag = document.createElement("span");
  tag.classList.add("badge", "text-bg-success", "rounded-pill", "and-tag");
  tag.textContent = "AND";
  divContainer.appendChild(tag);

  return { divContainer }
}

// OR tag factory
const orTag = () => {
  const divContainer = document.createElement("div");
  divContainer.classList.add("fs-5", "mt-2");
  const tag = document.createElement("span");
  tag.classList.add("badge", "text-bg-warning", "rounded-pill", "or-tag");
  tag.textContent = "OR";
  divContainer.appendChild(tag);

  return { divContainer }
}

// Big or tag
const bigOrTag = () => {
  const divContainer = document.createElement("div");
  divContainer.classList.add("fs-3", "d-flex");
  const tag = document.createElement("span");
  tag.classList.add("badge", "text-bg-success", "rounded-pill", "align-self-center", "big-or-tag");
  tag.textContent = "OR";
  divContainer.appendChild(tag);

  return { divContainer }
}

// filter tag factory used for tags inside Filter and Exclude Filter
const filterTag = (content, filterIdx) => {
  const divContainer = document.createElement("div");
  divContainer.classList.add("filter-tag");
  const buttonTag = document.createElement("button");
  buttonTag.classList.add("btn", "btn-outline-dark", "m-2");
  divContainer.appendChild(buttonTag)
  buttonTag.textContent = "X " + content;
  buttonTag.dataset.tagIdx = filterIdx;

  return { divContainer, content, buttonTag }
}

// unionFilter factory
const unionFilter = (filterNumber) => {
  const divContainer = document.createElement("div");
  divContainer.classList.add("py-3", "col-12", "div-filter-union");

  const containerCard = document.createElement("div");
  containerCard.classList.add("card", "border", "bg-info", "border-secondary", "border-opacity-100", "border-3", "rounded")

  const containerBody = document.createElement("div");
  containerBody.classList.add("card-body");

  const containerHeader = document.createElement("div");
  containerHeader.classList.add("d-flex", "justify-content-between");

  const titleFilter = document.createElement("h4");
  titleFilter.textContent = "Filter";

  const removeFilter = document.createElement("button");
  removeFilter.classList.add("btn", "btn-danger", "text-bold", "text-white");
  removeFilter.setAttribute("data-index", filterNumber);
  removeFilter.textContent = "X";

  if (filterNumber == 0) {
    removeFilter.classList.add("d-none");
  }

  const filterContainer = document.createElement("div");
  filterContainer.classList.add("card-text", "d-flex", "flex-wrap");
  filterContainer.setAttribute("style", "min-height: 10vh; max-height: 10vh; overflow-y: scroll;");
  filterContainer.setAttribute("id", `filter-container-${filterNumber}`);

  // Building the filter DOM
  divContainer.appendChild(containerCard);
  containerCard.appendChild(containerBody);
  containerBody.appendChild(containerHeader);
  containerHeader.appendChild(titleFilter);
  containerHeader.appendChild(removeFilter);
  containerBody.appendChild(filterContainer);

  let filterList = []; // Store the tuple filter

  let tagList = []; // Store the tag html elements

  return { divContainer, removeFilter, filterList, tagList };
};

//exclude filter factory
const excludeFilter = () => {
  const divContainer = document.createElement("div");
  divContainer.classList.add("py-3", "col-12");

  const containerCard = document.createElement("div");
  containerCard.classList.add("card", "border", "bg-danger", "border-danger", "bg-opacity-25", "border-3", "rounded")

  const containerBody = document.createElement("div");
  containerBody.classList.add("card-body");

  const containerHeader = document.createElement("div");
  containerHeader.classList.add("d-flex", "justify-content-between");

  const titleFilter = document.createElement("h4");
  titleFilter.textContent = "Exclude Filter";

  const filterContainer = document.createElement("div");
  filterContainer.classList.add("card-text", "d-flex", "flex-wrap");
  filterContainer.setAttribute("style", "min-height: 10vh; max-height: 10vh; overflow-y: scroll;");
  filterContainer.setAttribute("id", "exclude-filter");

  // Building the filter DOM
  divContainer.appendChild(containerCard);
  containerCard.appendChild(containerBody);
  containerBody.appendChild(containerHeader);
  containerHeader.appendChild(titleFilter);

  containerBody.appendChild(filterContainer);

  let filterList = []; // to store data filters

  let tagList = []; // to store DOM filtertags

  return { divContainer, filterList, tagList };
};

function updateFilterTagList(filterElement) {
  const n = filterElement.filterList.length;
  for (let i = 0; i < n; i++) {
    let tag = filterElement.tagList[i];
    tag.buttonTag.dataset.tagIdx = i;
  }
}

// Create a filterExclude and appending to the DOM
let filterExclude = excludeFilter();
const filterExcludeContainer = document.querySelector("#filter-exclude-container");
filterExcludeContainer.appendChild(filterExclude.divContainer);

// add functionality to exclude button
const buttonExclude = document.querySelector("#exclude-button");
buttonExclude.addEventListener("click", () => {
  const container = document.querySelector("#exclude-filter");
  const newFilter = document.querySelector("#text-filter");
  const yearFilter = document.querySelector("#year-filter");
  const filterType = document.querySelector("#type-filter");
  const topicValue = document.querySelector("#topic-value");
  const normValue = document.querySelector("#norm-filter");
  const descriptorValue = document.querySelector("#descriptor-filter");
  const chamberValue = document.querySelector("#chamber-filter");
  const nodecisionValue = document.querySelector("#nodecision-filter");
  const resultValue = document.querySelector("#result-filter");

  let contentType = filterType.value;

  let content;
  if (contentType == "Topic") {
    content = topicValue.value;
  }
  else if (contentType == "Norm") {
    content = normValue.value;
  }
  else if (contentType == "descriptors") {
    content = descriptorValue.value;
  }
  else if (contentType == "chamber") {
    content = chamberValue.value;
  }
  else if (contentType == "No_decis") {
    content = nodecisionValue.value;
  }
  else if (contentType == "Result") {
    content = resultValue.value;
  }
  else if (contentType == "year_range") {
    content = yearFilter.value;
  }
  else {
    content = newFilter.value;
  }

  if (content != "") {
    const filterIdx = filterExclude.filterList.length;
    let tag = filterTag(contentType + ": " + content, filterIdx);
    filterExclude.tagList.push(tag);
    container.appendChild(tag.divContainer);
    filterExclude.filterList.push([contentType, content]);
    tag.divContainer.addEventListener("click", (e) => {

      const idx = e.target.dataset.tagIdx;

      if (idx == 0) {
        filterExclude.filterList.shift();
        filterExclude.tagList.shift()
      }

      else {
        filterExclude.filterList.splice(idx, idx);
        filterExclude.tagList.splice(idx, idx)
      }

      updateFilterTagList(filterExclude)
      container.removeChild(e.target.parentElement);
      inputData.update();
      //inputData.show(); // used for debbuging
      removeOrConnectors();
      addOrConnectors();
    })
  }
  inputData.update();
  //inputData.show(); // used for debbuging
  removeOrConnectors();
  addOrConnectors();
})

const buttonAdd = document.querySelector("#add-button");
buttonAdd.addEventListener("click", () => {
  const newFilter = document.querySelector("#text-filter");
  const yearFilter = document.querySelector("#year-filter");
  const filterType = document.querySelector("#type-filter");
  const topicValue = document.querySelector("#topic-value");
  const normValue = document.querySelector("#norm-filter");
  const descriptorValue = document.querySelector("#descriptor-filter");
  const chamberValue = document.querySelector("#chamber-filter");
  const container = document.querySelector(`#filter-container-${activeFilter}`);
  const nodecisionValue = document.querySelector("#nodecision-filter");
  const resultValue = document.querySelector("#result-filter");

  let contentType = filterType.value;

  let content;

  if (contentType == "Topic") {
    content = topicValue.value;
  }

  else if (contentType == "Norm") {
    content = normValue.value;
  }

  else if (contentType == "descriptors") {
    content = descriptorValue.value;
  }

  else if (contentType == "chamber") {
    content = chamberValue.value;
  }
  else if (contentType == "No_decis") {
    content = nodecisionValue.value;
  }

  else if (contentType == "Result") {
    content = resultValue.value;
  }
  else if (contentType == "year_range") {
    content = yearFilter.value;
  }
  else {
    content = newFilter.value;
  }

  if (content != "") {
    const filterIdx = unionFilterList[activeFilter].filterList.length;
    const tag = filterTag(contentType + ": " + content, filterIdx);
    unionFilterList[activeFilter].tagList.push(tag);
    container.appendChild(tag.divContainer);
    unionFilterList[activeFilter].filterList.push([contentType, content]);
    tag.divContainer.addEventListener("click", (e) => {
      parentContainer = e.target.parentElement.parentElement.parentElement;
      buttonContainer = parentContainer.querySelector(".btn.btn-danger");
      const filterIdx = buttonContainer.dataset.index;
      const idx = e.target.dataset.tagIdx;

      if (idx == 0) {
        unionFilterList[filterIdx].filterList.shift();
        unionFilterList[filterIdx].tagList.shift()
      }

      else {
        unionFilterList[filterIdx].filterList.splice(idx, idx);
        unionFilterList[filterIdx].tagList.splice(idx, idx);
      }

      activeFilter = filterIdx;
      updateFilterTagList(unionFilterList[activeFilter]);
      updateActiveFilter(activeFilter);
      container.removeChild(e.target.parentElement);
      e.stopImmediatePropagation();
      inputData.update();
      removeConnectors();
      addConnectors();
      //inputData.show(); // used for debbuging
    })
    inputData.update();
    //inputData.show(); // used for debbuging
    removeConnectors();
    addConnectors();
  }
});

// To update the data index after removing an element
function updateFilterList(FilterList) {
  const n = FilterList.length;
  for (let i = 0; i < n; i++) {
    FilterList[i].removeFilter.dataset.index = i;
  }
}

// update filter container data index and border color
function updateActiveFilter(idx) {
  const n = unionFilterList.length;
  for (let i = 0; i < n; i++) {
    let filterList = unionFilterList[i].divContainer.firstChild;
    if (i == idx) {
      if (!filterList.classList.contains("border-opacity-100")) {
        filterList.classList.remove("border-opacity-50");
        filterList.classList.add("border-opacity-100");
      }
    }
    else {
      if (filterList.classList.contains("border-opacity-100")) {
        filterList.classList.remove("border-opacity-100");
        filterList.classList.add("border-opacity-50")
      }
    }

    let filterContainer = filterList.querySelector('div[id^="filter-container"]');
    filterContainer.setAttribute("id", `filter-container-${i}`)
  }

}

// add AND-tags between tags union filters
function addConnectors() {
  for (filter of unionFilterList) {
    const tagFilters = filter.divContainer.querySelectorAll(".filter-tag");
    const n = tagFilters.length;

    for (let i = 1; i < n; i++) {
      const andTagFilter = andTag();
      tagFilters[i].parentElement.insertBefore(andTagFilter.divContainer, tagFilters[i])
    }
  }
}

// remove AND-tags between tags filters
function removeConnectors() {
  const andTags = document.querySelectorAll(".and-tag");
  andTags.forEach(e => {
    e.parentElement.parentElement.removeChild(e.parentElement)
  })
}

// add OR-tags between tags inside exclude filter
function addOrConnectors() {
  const tagFilters = filterExclude.divContainer.querySelectorAll(".filter-tag");
  const n = tagFilters.length;

  for (let i = 1; i < n; i++) {
    const orTagFilter = orTag();
    tagFilters[i].parentElement.insertBefore(orTagFilter.divContainer, tagFilters[i])
  }
}

// add OR-tags between tags inside exclude filter
function removeOrConnectors() {
  const andTags = document.querySelectorAll(".or-tag");
  andTags.forEach(e => {
    e.parentElement.parentElement.removeChild(e.parentElement)
  })
}

// add Big Or-tags between Union Filter
function addBigOrConnectors() {
  const filtersContainer = document.querySelector("#filter-union-container");
  const filters = filtersContainer.querySelectorAll(".div-filter-union");
  const n = filters.length;
  for (let i = 1; i < n; i++) {
    const bigOrTagFilter = bigOrTag();
    filters[i].parentElement.insertBefore(bigOrTagFilter.divContainer, filters[i])
  }
}

// remove Big Or-tags between Union Filter
function removeBigOrConnectors() {
  const andTags = document.querySelectorAll(".big-or-tag");
  andTags.forEach(e => {
    e.parentElement.parentElement.removeChild(e.parentElement)
  })
}


// List of filter to send in the post
let unionFilterList = [];
let activeFilter = -1; // Active filter index

// Add event listener to create filter button
const buttonCreate = document.querySelector("#create-filter");
buttonCreate.addEventListener("click", () => {
  // Creating a new filter and adding it to the DOM
  const filterUnionContainer = document.querySelector("#filter-union-container");
  let idx = unionFilterList.length;
  activeFilter = idx;
  let newFilter = unionFilter(idx);
  unionFilterList.push(newFilter);
  filterUnionContainer.appendChild(newFilter.divContainer);
  updateActiveFilter(activeFilter);
  if (idx > 0) {
    document.getElementById("refine-title").scrollIntoView();
  }

  // allow to active filter when click on the container
  newFilter.divContainer.addEventListener("click", (e) => {
    parentContainer = e.target.parentElement.parentElement.parentElement;
    const button = parentContainer.querySelector(".btn.btn-danger");
    const idx = button.dataset.index;
    activeFilter = idx;
    updateActiveFilter(activeFilter);
  })

  // adding remove function
  newFilter.removeFilter.addEventListener("click", (e) => {
    const parent = e.target.parentElement.parentElement.parentElement
    const idx = e.target.dataset.index;
    filterUnionContainer.removeChild(parent.parentElement);
    if (idx == 0) {
      unionFilterList.shift();
    }
    else {
      unionFilterList.splice(idx, idx);
    }
    updateFilterList(unionFilterList);
    activeFilter = unionFilterList.length - 1;
    updateActiveFilter(activeFilter);

    e.stopImmediatePropagation();
    inputData.update();
    //inputData.show(); // used for debbuging
    removeBigOrConnectors();
    addBigOrConnectors();
  })
  inputData.update();
  //inputData.show(); // used for debbuging
  removeBigOrConnectors();
  addBigOrConnectors();

})
document.addEventListener('DOMContentLoaded', function () {
  const typeFilter = document.getElementById('type-filter');
  const yearFilter = document.getElementById('year-filter');
  const textFilter = document.getElementById('text-filter');
  const normFilter = document.getElementById('norm-filter');
  const descriptorFilter = document.getElementById('descriptor-filter');
  const chamberFilter = document.getElementById('chamber-filter');
  const nodecisionFilter = document.getElementById('nodecision-filter');
  const resultFilter = document.getElementById('result-filter');
  const topicValue = document.getElementById('topic-value');
  const addButton = document.getElementById('add-button');
  const excludeButton = document.getElementById('exclude-button');
  const errorMessage = document.getElementById('validation-error-message');

  // Hide all filters initially
  textFilter.style.display = 'none';
  yearFilter.style.display = 'none';
  normFilter.style.display = 'none';
  descriptorFilter.style.display = 'none';
  chamberFilter.style.display = 'none';
  nodecisionFilter.style.display = 'none';
  resultFilter.style.display = 'none';
  topicValue.style.display = 'none';

  // Initialize buttons as enabled
  addButton.disabled = false;
  excludeButton.disabled = false;

  // Function to handle filter visibility based on the selected filter type
  function handleFilterChange() {
    const selectedFilter = typeFilter.value;

    // Hide all filters first
    textFilter.style.display = 'none';
    yearFilter.style.display = 'none';
    normFilter.style.display = 'none';
    descriptorFilter.style.display = 'none';
    chamberFilter.style.display = 'none';
    nodecisionFilter.style.display = 'none';
    resultFilter.style.display = 'none';
    topicValue.style.display = 'none';

    // Show the appropriate filter based on the selected type
    if (selectedFilter === 'year_range') {
      yearFilter.style.display = 'block';

      yearFilter.addEventListener('input', function () {
        const yearRange = this.value;
        const yearRangePattern = /^(\d{4})(?:-(\d{4}))?$/;

        const match = yearRange.match(yearRangePattern);
        if (!match) {
          errorMessage.textContent = 'Invalid format. Use YYYY or YYYY-YYYY (e.g., 2020 or 2017-2022).';
          errorMessage.style.display = 'block';  // Show format error message
          addButton.disabled = true;  // Disable buttons
          excludeButton.disabled = true;
        } else {
          const startYear = parseInt(match[1], 10);
          const endYear = match[2] ? parseInt(match[2], 10) : startYear; // Handle single year as range

          if (endYear < startYear) {
            errorMessage.textContent = 'The final year cannot be earlier than the start year.';
            errorMessage.style.display = 'block';  // Show range error message
            addButton.disabled = true;  // Disable buttons
            excludeButton.disabled = true;
          } else {
            errorMessage.style.display = 'none';  // Hide the error message
            addButton.disabled = false;  // Enable buttons
            excludeButton.disabled = false;
          }
        }
      });
    } else {
      // Show the appropriate filter based on the selected type
      if (selectedFilter === 'Norm') normFilter.style.display = 'block';
      if (selectedFilter === 'descriptors') descriptorFilter.style.display = 'block';
      if (selectedFilter === 'chamber') chamberFilter.style.display = 'block';
      if (selectedFilter === 'No_decis') nodecisionFilter.style.display = 'block';
      if (selectedFilter === 'Result') resultFilter.style.display = 'block';
      if (selectedFilter === 'Topic') topicValue.style.display = 'block';
      if (selectedFilter === 'Keyword') textFilter.style.display = 'block';
    }
  }

  // Attach event listener for filter type changes
  typeFilter.addEventListener('change', handleFilterChange);

  // Initialize the filters and button state on page load
  handleFilterChange();
});
