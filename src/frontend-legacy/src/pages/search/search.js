import { useMemo, useState } from "react";

import {
  convertToBooleanQuery,
  createSearchProject,
  previewSearch,
} from "../../libs/search";

const DEFAULT_SEARCH_SOURCES = [
  {
    label: "Chambre Administrative",
    value: "chambre_administrative",
  },
  {
    label: "Chambre Penale",
    value: "chambre_penale",
  },
  {
    label: "Chambre Civile",
    value: "chambre_civile",
  },
];

function todayAsISODate() {
  return new Date().toISOString().slice(0, 10);
}

function buildInitialFormState(sources) {
  return {
    naturalLanguageQuery: "",
    projectName: "",
    query: "",
    rangeBeginDate: "2000-01-01",
    rangeEndDate: todayAsISODate(),
    selectedIndices: sources[0] ? [sources[0].value] : [],
  };
}

function SearchConfirmationModal({ isSubmitting, preview, onCancel, onContinue }) {
  if (!preview) {
    return null;
  }

  let alertClassName = "alert-success";
  let previewMessage = `The number of estimated documents is ${preview.total_documents}. Would you like to continue with this query?`;

  if (preview.total_documents === 0) {
    alertClassName = "alert-danger";
    previewMessage =
      "There are no estimated documents for this query. Please specify a different one.";
  } else if (!preview.can_cluster) {
    alertClassName = "alert-warning";
    previewMessage = `The number of estimated documents is ${preview.total_documents}. The project can be created, but the documents will not be clustered (minimum number of documents for clustering: ${preview.clustering_min_documents}). Would you like to continue with this query?`;
  }

  return (
    <>
      <div className="modal-backdrop fade show" />
      <div
        aria-labelledby="search-confirmation-title"
        aria-modal="true"
        className="modal d-block"
        role="dialog"
        tabIndex="-1"
      >
        <div className="modal-dialog">
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title fs-5" id="search-confirmation-title">
                Confirm project creation
              </h2>
              <button
                aria-label="Close"
                className="btn-close"
                onClick={onCancel}
                type="button"
              />
            </div>
            <div className="modal-body">
              <div className={`alert ${alertClassName}`} role="alert">
                {previewMessage}
              </div>
              <ul className="list-group">
                <li className="list-group-item">
                  <strong>Project name:</strong> {preview.project_name}
                </li>
                <li className="list-group-item">
                  <strong>Search:</strong> {preview.query}
                </li>
                <li className="list-group-item">
                  <strong>From:</strong> {preview.range_begin_date}
                </li>
                <li className="list-group-item">
                  <strong>To:</strong> {preview.range_end_date}
                </li>
              </ul>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={onCancel} type="button">
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={isSubmitting || !preview.can_continue}
                onClick={onContinue}
                type="button"
              >
                {isSubmitting ? "Starting..." : "Continue"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function SearchAlerts({ errors, preview, success }) {
  return (
    <div className="mt-4">
      {success ? (
        <div className="alert alert-success" role="alert">
          {success.detail}{" "}
          {success.urls?.running ? (
            <a href={success.urls.running}>View running projects</a>
          ) : null}
        </div>
      ) : null}
      {preview ? (
        <div
          className={`alert ${
            preview.total_documents === 0
              ? "alert-danger"
              : preview.can_cluster
              ? "alert-primary"
              : "alert-warning"
          }`}
          role="status"
        >
          {preview.total_documents} document
          {preview.total_documents !== 1 ? "s" : ""} evaluated
          {!preview.can_cluster && preview.total_documents > 0
            ? ` - fewer than the ${preview.clustering_min_documents} required for clustering.`
            : "."}
        </div>
      ) : null}
      {errors.map((errorMessage) => (
        <div className="alert alert-danger" key={errorMessage} role="alert">
          {errorMessage}
        </div>
      ))}
    </div>
  );
}

function Search({ context }) {
  const searchConfig = context.search ?? {};
  const sources = useMemo(() => {
    if (Array.isArray(searchConfig.sources) && searchConfig.sources.length > 0) {
      return searchConfig.sources;
    }

    return DEFAULT_SEARCH_SOURCES;
  }, [searchConfig.sources]);

  const [formState, setFormState] = useState(() => buildInitialFormState(sources));
  const [errors, setErrors] = useState([]);
  const [preview, setPreview] = useState(null);
  const [success, setSuccess] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  function setFormValue(field, value) {
    setFormState((currentValue) => ({
      ...currentValue,
      [field]: value,
    }));
  }

  function applyValidatedPayload(payload) {
    setFormState((currentValue) => ({
      ...currentValue,
      projectName: payload.project_name,
      query: payload.query,
      naturalLanguageQuery: payload.natural_language_query,
      rangeBeginDate: payload.range_begin_date,
      rangeEndDate: payload.range_end_date,
      selectedIndices: payload.selected_indices,
    }));
  }

  function buildPayload() {
    return {
      natural_language_query: formState.naturalLanguageQuery,
      project_name: formState.projectName,
      query: formState.query,
      range_begin_date: formState.rangeBeginDate,
      range_end_date: formState.rangeEndDate,
      selected_indices: formState.selectedIndices,
    };
  }

  function handleRequestError(error) {
    setErrors(error.messages ?? [error.message]);
  }

  async function handleTranslateQuery() {
    setErrors([]);
    setSuccess(null);
    setIsTranslating(true);

    try {
      const response = await convertToBooleanQuery(
        context.api,
        formState.naturalLanguageQuery
      );
      setFormValue("query", response.query);
    } catch (error) {
      handleRequestError(error);
    } finally {
      setIsTranslating(false);
    }
  }

  async function handlePreviewSearch() {
    setErrors([]);
    setSuccess(null);
    setConfirmation(null);
    setIsEvaluating(true);

    try {
      const response = await previewSearch(context.api, buildPayload());
      applyValidatedPayload(response);
      setPreview(response);
    } catch (error) {
      setPreview(null);
      handleRequestError(error);
    } finally {
      setIsEvaluating(false);
    }
  }

  async function handleOpenConfirmation() {
    setErrors([]);
    setSuccess(null);
    setIsEvaluating(true);

    try {
      const response = await previewSearch(context.api, buildPayload());
      applyValidatedPayload(response);
      setPreview(response);
      setConfirmation(response);
    } catch (error) {
      setConfirmation(null);
      handleRequestError(error);
    } finally {
      setIsEvaluating(false);
    }
  }

  async function handleCreateProject() {
    setErrors([]);
    setIsCreating(true);

    try {
      const response = await createSearchProject(context.api, buildPayload());
      setSuccess(response);
      setPreview(null);
      setConfirmation(null);
    } catch (error) {
      handleRequestError(error);
    } finally {
      setIsCreating(false);
    }
  }

  if (!context.user.isAuthenticated) {
    return (
      <section className="container py-5 mt-5">
        <div className="alert alert-warning mt-5" role="alert">
          Please <a href={context.urls.login}>log in</a> to create and evaluate
          search projects.
        </div>
      </section>
    );
  }

  return (
    <>
      <section className="container d-flex flex-grow-1 py-4 mt-5 justify-content-center">
        <div className="search-block col-xl-8 mx-auto pt-4">
          <h1 className="text-center mb-4 text-dark">
            <i className="fa-solid fa-magnifying-glass me-3" />
            Project Search
          </h1>

          <div className="card shadow-sm border-0">
            <div className="card-body p-4 p-lg-5">
              <div className="row mb-4">
                <div className="col-12">
                  <label className="form-label" htmlFor="project-name-input">
                    Project Name
                  </label>
                  <input
                    className="fs-5 form-control"
                    id="project-name-input"
                    onChange={(event) =>
                      setFormValue("projectName", event.target.value)
                    }
                    placeholder="Project Name"
                    type="text"
                    value={formState.projectName}
                  />
                </div>
              </div>

              <div className="accordion py-3" id="search-page-accordion">
                <div className="accordion-item">
                  <h2 className="accordion-header" id="search-page-sources-heading">
                    <button
                      aria-controls="search-page-sources"
                      aria-expanded="true"
                      className="accordion-button text-center"
                      data-bs-target="#search-page-sources"
                      data-bs-toggle="collapse"
                      type="button"
                    >
                      Source and Search Terms
                    </button>
                  </h2>
                  <div
                    aria-labelledby="search-page-sources-heading"
                    className="accordion-collapse collapse show"
                    id="search-page-sources"
                  >
                    <div className="accordion-body row col-11 mx-auto py-3">
                      <div className="col-lg-6 text-start py-2">
                        <h2 className="h6">
                          <i className="bi bi-database me-2" />
                          Select Source
                        </h2>
                        <div className="form-check ps-sm-5 text-start">
                          {sources.map((source) => (
                            <div className="form-check" key={source.value}>
                              <input
                                checked={formState.selectedIndices.includes(source.value)}
                                className="form-check-input"
                                id={`source-${source.value}`}
                                name="search-source"
                                onChange={() =>
                                  setFormValue("selectedIndices", [source.value])
                                }
                                type="radio"
                                value={source.value}
                              />
                              <label
                                className="form-check-label"
                                htmlFor={`source-${source.value}`}
                              >
                                {source.label}
                              </label>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="row mt-3 justify-content-center">
                        <div className="col-md-12">
                          <label className="form-label" htmlFor="natural-language-query">
                            Natural Language Query
                          </label>
                          <textarea
                            className="fs-5 form-control"
                            id="natural-language-query"
                            onChange={(event) =>
                              setFormValue(
                                "naturalLanguageQuery",
                                event.target.value
                              )
                            }
                            placeholder="Write your question (e.g., 'Quels sont les droits du locataire en cas d'expulsion ?')"
                            rows="3"
                            value={formState.naturalLanguageQuery}
                          />
                        </div>
                      </div>

                      <div className="row mt-3 justify-content-center">
                        <div className="col-12 col-md-6 mb-2 m-2 me-2 justify-content-center">
                          <button
                            className="btn btn-primary w-100 mt-2"
                            disabled={
                              isTranslating || !formState.naturalLanguageQuery.trim()
                            }
                            onClick={handleTranslateQuery}
                            type="button"
                          >
                            <i className="bi bi-gear-fill me-2" />
                            {isTranslating
                              ? "Building Boolean Query..."
                              : "Build Boolean Query"}
                          </button>
                        </div>
                      </div>

                      <div className="row mt-3 justify-content-center">
                        <div className="col-12">
                          <label className="form-label" htmlFor="boolean-query">
                            Boolean Query
                          </label>
                          <textarea
                            className="fs-5 form-control"
                            id="boolean-query"
                            onChange={(event) =>
                              setFormValue("query", event.target.value)
                            }
                            placeholder={'Enter your boolean query (e.g., "contrat" AND "résiliation" NOT "litige")'}
                            rows="3"
                            value={formState.query}
                          />
                        </div>
                      </div>

                      <div className="row mt-4 justify-content-center">
                        <div className="col-md-5">
                          <label className="form-label" htmlFor="range-begin-date">
                            Decision Date From
                          </label>
                          <input
                            className="form-control"
                            id="range-begin-date"
                            onChange={(event) =>
                              setFormValue("rangeBeginDate", event.target.value)
                            }
                            type="date"
                            value={formState.rangeBeginDate}
                          />
                        </div>
                        <div className="col-md-2" />
                        <div className="col-md-5 mt-3 mt-md-0">
                          <label className="form-label" htmlFor="range-end-date">
                            Decision Date To
                          </label>
                          <input
                            className="form-control"
                            id="range-end-date"
                            onChange={(event) =>
                              setFormValue("rangeEndDate", event.target.value)
                            }
                            type="date"
                            value={formState.rangeEndDate}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="row mt-4 g-3 justify-content-center">
                <div className="col-md-4">
                  <button
                    className="btn btn-outline-secondary w-100"
                    disabled={isEvaluating || isCreating}
                    onClick={handlePreviewSearch}
                    type="button"
                  >
                    <i className="bi bi-clipboard-check me-2" />
                    {isEvaluating ? "Evaluating..." : "Evaluate"}
                  </button>
                </div>
                <div className="col-md-4">
                  <button
                    className="btn btn-primary w-100"
                    disabled={isEvaluating || isCreating}
                    onClick={handleOpenConfirmation}
                    type="button"
                  >
                    <i className="bi bi-folder-plus me-2" />
                    Create Project
                  </button>
                </div>
              </div>

              <SearchAlerts errors={errors} preview={preview} success={success} />
            </div>
          </div>
        </div>
      </section>

      <SearchConfirmationModal
        isSubmitting={isCreating}
        onCancel={() => setConfirmation(null)}
        onContinue={handleCreateProject}
        preview={confirmation}
      />
    </>
  );
}

export default Search;
