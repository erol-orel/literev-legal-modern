import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { deleteProject } from "../../libs/projects";
import {
  askTopDocuments,
  createProjectRefinement,
  deleteProjectRefinement,
  fetchProjectOverview,
  generateProjectClusterSummary,
  previewProjectFilters,
} from "../../libs/project_overview";
import { staticAsset } from "../../libs/static";

const YEAR_RANGE_PATTERN = /^\d{4}(-\d{4})?$/;
const bokehLoaderCache = new Map();

function formatDate(value) {
  return value || "-";
}

function buildInitialDraft(filterTypes) {
  const firstFilterType = filterTypes[0];
  if (!firstFilterType) {
    return { type: "", value: "" };
  }

  if (
    firstFilterType.input_kind === "select" &&
    Array.isArray(firstFilterType.options) &&
    firstFilterType.options.length > 0
  ) {
    return {
      type: firstFilterType.value,
      value: firstFilterType.options[0].value,
    };
  }

  return {
    type: firstFilterType.value,
    value: "",
  };
}

function extractScriptContent(scriptMarkup) {
  return scriptMarkup
    .replace(/<script[^>]*>/i, "")
    .replace(/<\/script>/i, "")
    .trim();
}

function loadExternalScript(src) {
  if (!src) {
    return Promise.resolve();
  }

  if (bokehLoaderCache.has(src)) {
    return bokehLoaderCache.get(src);
  }

  const existingScript = document.querySelector(`script[src="${src}"]`);
  if (existingScript?.dataset.loaded === "true") {
    const promise = Promise.resolve();
    bokehLoaderCache.set(src, promise);
    return promise;
  }

  const promise = new Promise((resolve, reject) => {
    const scriptElement = existingScript || document.createElement("script");

    function handleLoad() {
      scriptElement.dataset.loaded = "true";
      resolve();
    }

    function handleError() {
      reject(new Error(`Unable to load script: ${src}`));
    }

    scriptElement.addEventListener("load", handleLoad, { once: true });
    scriptElement.addEventListener("error", handleError, { once: true });

    if (!existingScript) {
      scriptElement.async = true;
      scriptElement.src = src;
      document.body.appendChild(scriptElement);
    }
  });

  bokehLoaderCache.set(src, promise);
  return promise;
}

function DeleteProjectModal({ isSubmitting, project, onCancel, onConfirm }) {
  if (!project) {
    return null;
  }

  return (
    <>
      <div className="modal-backdrop fade show" />
      <div
        aria-labelledby="project-delete-title"
        aria-modal="true"
        className="modal d-block"
        role="dialog"
        tabIndex="-1"
      >
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title fs-5" id="project-delete-title">
                Delete Project
              </h2>
              <button
                aria-label="Close"
                className="btn-close"
                onClick={onCancel}
                type="button"
              />
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete the following project?</p>
              <div className="ms-3">Project: {project.name}</div>
              <div className="ms-3 mb-3">Query: {project.query || "No query"}</div>
              <p>
                This action cannot be undone. Deleting this project will
                permanently remove it.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={onCancel} type="button">
                Close
              </button>
              <button
                className="btn btn-danger"
                disabled={isSubmitting}
                onClick={onConfirm}
                type="button"
              >
                {isSubmitting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function RefinementConfirmationModal({
  initialName,
  isSubmitting,
  preview,
  onCancel,
  onConfirm,
}) {
  const [refinementName, setRefinementName] = useState(initialName || "");

  useEffect(() => {
    setRefinementName(initialName || "");
  }, [initialName]);

  if (!preview) {
    return null;
  }

  const canContinue =
    preview.number_documents > 0 && refinementName.trim().length > 0;

  return (
    <>
      <div className="modal-backdrop fade show" />
      <div
        aria-labelledby="refinement-confirmation-title"
        aria-modal="true"
        className="modal d-block"
        role="dialog"
        tabIndex="-1"
      >
        <div className="modal-dialog">
          <div className="modal-content">
            <div className="modal-header">
              <h2
                className="modal-title fs-5"
                id="refinement-confirmation-title"
              >
                Confirm refinement creation
              </h2>
              <button
                aria-label="Close"
                className="btn-close"
                onClick={onCancel}
                type="button"
              />
            </div>
            <div className="modal-body">
              <div
                className={`alert ${
                  preview.number_documents > 0
                    ? "alert-success"
                    : "alert-danger"
                }`}
                role="alert"
              >
                {preview.number_documents > 0
                  ? `The refinement contains ${preview.number_documents} documents.`
                  : "This refinement does not contain any documents."}
              </div>
              <label className="form-label" htmlFor="refinement-name-input">
                Refinement name
              </label>
              <input
                className="form-control"
                id="refinement-name-input"
                onChange={(event) => setRefinementName(event.target.value)}
                type="text"
                value={refinementName}
              />
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={onCancel} type="button">
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={isSubmitting || !canContinue}
                onClick={() => onConfirm(refinementName.trim())}
                type="button"
              >
                {isSubmitting ? "Creating..." : "Continue"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function BokehPlot({ plot }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!plot?.div_plot || !plot?.script_plot || !containerRef.current) {
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
      return undefined;
    }

    let isMounted = true;
    const container = containerRef.current;

    async function renderPlot() {
      try {
        await loadExternalScript(staticAsset("js/bokeh.min.js"));
        if (!isMounted) {
          return;
        }

        container.innerHTML = plot.div_plot;
        const scriptElement = document.createElement("script");
        scriptElement.type = "text/javascript";
        scriptElement.text = extractScriptContent(plot.script_plot);
        container.appendChild(scriptElement);
      } catch {
        if (isMounted) {
          container.innerHTML =
            '<div class="alert alert-warning">The cluster plot is not available right now.</div>';
        }
      }
    }

    renderPlot();

    return () => {
      isMounted = false;
      container.innerHTML = "";
    };
  }, [plot]);

  return <div ref={containerRef} />;
}

function ClusterSummaryTable({
  clusterSummaries,
  generatingClusterId,
  onGenerateSummary,
}) {
  if (!clusterSummaries.length) {
    return null;
  }

  return (
    <div className="container mb-5">
      <h3 className="text-center mb-3">Cluster Summary Table</h3>
      <div className="table-responsive">
        <table className="table align-middle">
          <thead>
            <tr>
              <th scope="col">Cluster Number</th>
              <th scope="col" />
              <th scope="col">Topic</th>
              <th scope="col">Summary</th>
              <th scope="col">Total Documents</th>
              <th scope="col">Representative Document</th>
            </tr>
          </thead>
          <tbody>
            {clusterSummaries.map((summary) => (
              <tr
                key={summary.cluster_id}
                style={{
                  backgroundColor: `${summary.topic_color || "#e9ecef"}15`,
                }}
              >
                <td className="align-middle py-4 fs-2 text-center">
                  {summary.cluster_order >= 0 ? summary.cluster_order : ""}
                </td>
                <td className="align-middle px-4">
                  <span
                    className="d-inline-block rounded-circle"
                    style={{
                      backgroundColor: summary.topic_color || "#ced4da",
                      height: "30px",
                      width: "30px",
                    }}
                  />
                </td>
                <td className="align-middle py-4">{summary.topic_label}</td>
                <td className="py-4">
                  {summary.summary_text ? (
                    summary.summary_text
                  ) : (
                    <div>
                      <div className="alert alert-light shadow-sm" role="alert">
                        We couldn't generate a summary at the moment. Please try
                        again by clicking the button below.
                      </div>
                      <div className="text-end">
                        <button
                          className="btn btn-secondary"
                          disabled={generatingClusterId === summary.cluster_id}
                          onClick={() => onGenerateSummary(summary.cluster_id)}
                          type="button"
                        >
                          {generatingClusterId === summary.cluster_id
                            ? "Generating..."
                            : "Generate"}
                        </button>
                      </div>
                    </div>
                  )}
                </td>
                <td className="py-4 px-2">{summary.total_documents}</td>
                <td className="py-4 px-2">
                  {summary.representative_document ? (
                    <>
                      <div>
                        <i>Document ID:</i>{" "}
                        <b>{summary.representative_document.document_id}</b>
                      </div>
                      <div>
                        <i>Procedure Type:</i>{" "}
                        <b>{summary.representative_document.procedure_type}</b>
                      </div>
                      <div>
                        <i>Decision Type:</i>{" "}
                        <b>{summary.representative_document.decision_type}</b>
                      </div>
                      <div>
                        <i>Result:</i>{" "}
                        <b>{summary.representative_document.result}</b>
                      </div>
                    </>
                  ) : (
                    <p className="mb-0">N/A</p>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilterConditionButton({ label, onRemove }) {
  return (
    <button className="btn btn-outline-dark m-2" onClick={onRemove} type="button">
      X {label}
    </button>
  );
}

function RefinementHistory({ onDelete, refinements }) {
  if (!refinements.length) {
    return null;
  }

  return (
    <div className="container mb-5 fs-5">
      <div className="fw-bold fs-3 text-center mb-3">Refinement history</div>
      <div className="table-responsive">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Owner</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {refinements.map((refinement) => (
              <tr key={refinement.id}>
                <th scope="row">
                  <a className="btn btn-outline-secondary my-2" href={refinement.open_url}>
                    {refinement.name}
                  </a>
                </th>
                <td className="align-middle">{refinement.owner_name}</td>
                <td className="align-middle">
                  {refinement.can_delete ? (
                    <button
                      className="btn btn-outline-danger my-2"
                      onClick={() => onDelete(refinement.id)}
                      type="button"
                    >
                      Remove
                    </button>
                  ) : (
                    <span className="badge text-bg-secondary">Shared</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Project({ context }) {
  const { projectId } = useParams();
  const [deleteModalProject, setDeleteModalProject] = useState(null);
  const [draft, setDraft] = useState({ type: "", value: "" });
  const [errors, setErrors] = useState([]);
  const [generatingClusterId, setGeneratingClusterId] = useState(null);
  const [isCreatingRefinement, setIsCreatingRefinement] = useState(false);
  const [isDeletingProject, setIsDeletingProject] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isStartingTopDocs, setIsStartingTopDocs] = useState(false);
  const [overview, setOverview] = useState(null);
  const [preview, setPreview] = useState(null);
  const [successMessage, setSuccessMessage] = useState("");
  const [unionFilters, setUnionFilters] = useState([[]]);
  const [excludeFilters, setExcludeFilters] = useState([]);
  const [yearRangeError, setYearRangeError] = useState("");

  const filterTypes = useMemo(() => overview?.filters?.types ?? [], [overview?.filters?.types]);
  const currentFilterType = useMemo(
    () =>
      filterTypes.find((filterType) => filterType.value === draft.type) ||
      filterTypes[0] ||
      null,
    [draft.type, filterTypes]
  );

  useEffect(() => {
    if (!currentFilterType && filterTypes.length === 0) {
      return;
    }

    if (!draft.type && filterTypes.length > 0) {
      setDraft(buildInitialDraft(filterTypes));
    }
  }, [currentFilterType, draft.type, filterTypes]);

  useEffect(() => {
    if (overview?.project?.name) {
      document.title = `LiteRev Legal | ${overview.project.name}`;
    }
  }, [overview]);

  useEffect(() => {
    async function loadOverview() {
      setErrors([]);
      setIsLoading(true);

      try {
        const response = await fetchProjectOverview(context.api, projectId);
        if (response.redirect_url) {
          window.location.assign(response.redirect_url);
          return;
        }
        setOverview(response);
      } catch (error) {
        setErrors(error.messages ?? [error.message]);
      } finally {
        setIsLoading(false);
      }
    }

    loadOverview();
  }, [context.api, projectId]);

  function normalizeDraftValue(filterType, value) {
    const normalizedValue = value.trim();
    if (!filterType || !normalizedValue) {
      return { error: "", value: normalizedValue };
    }

    if (filterType.value === "year_range") {
      if (!YEAR_RANGE_PATTERN.test(normalizedValue)) {
        return {
          error:
            "Enter a year as YYYY or a range as YYYY-YYYY (e.g., 2020 or 2017-2022).",
          value: normalizedValue,
        };
      }

      if (normalizedValue.includes("-")) {
        const [startYear, endYear] = normalizedValue.split("-").map(Number);
        if (startYear > endYear) {
          return {
            error: "The end year must be greater than or equal to the start year.",
            value: normalizedValue,
          };
        }
      }
    }

    return { error: "", value: normalizedValue };
  }

  function buildCondition(filterType, value) {
    const option = (filterType.options ?? []).find(
      (filterOption) => filterOption.value === value
    );
    const optionLabel = option?.label || value;
    return {
      key: filterType.value,
      label: `${filterType.label}: ${optionLabel}`,
      value,
    };
  }

  function handleTypeChange(nextTypeValue) {
    const nextFilterType = filterTypes.find(
      (filterType) => filterType.value === nextTypeValue
    );
    if (!nextFilterType) {
      setDraft({ type: nextTypeValue, value: "" });
      return;
    }

    if (
      nextFilterType.input_kind === "select" &&
      Array.isArray(nextFilterType.options) &&
      nextFilterType.options.length > 0
    ) {
      setDraft({
        type: nextTypeValue,
        value: nextFilterType.options[0].value,
      });
      return;
    }

    setDraft({ type: nextTypeValue, value: "" });
  }

  function handleAddCondition(target) {
    if (!currentFilterType) {
      return;
    }

    const normalizedDraft = normalizeDraftValue(
      currentFilterType,
      draft.value
    );
    setYearRangeError(normalizedDraft.error);
    if (!normalizedDraft.value || normalizedDraft.error) {
      return;
    }

    const nextCondition = buildCondition(currentFilterType, normalizedDraft.value);
    if (target === "exclude") {
      setExcludeFilters((currentValue) => [...currentValue, nextCondition]);
    } else {
      setUnionFilters((currentValue) => {
        const nextFilters = [...currentValue];
        if (nextFilters.length === 0) {
          return [[nextCondition]];
        }
        const nextGroup = [...nextFilters[nextFilters.length - 1], nextCondition];
        nextFilters[nextFilters.length - 1] = nextGroup;
        return nextFilters;
      });
    }

    if (currentFilterType.input_kind !== "select") {
      setDraft((currentValue) => ({ ...currentValue, value: "" }));
    }
  }

  function handleCreateUnionFilter() {
    setUnionFilters((currentValue) => {
      const lastGroup = currentValue[currentValue.length - 1] || [];
      if (lastGroup.length === 0) {
        return currentValue;
      }
      return [...currentValue, []];
    });
  }

  function removeUnionCondition(groupIndex, conditionIndex) {
    setUnionFilters((currentValue) => {
      const nextFilters = currentValue.map((group, index) => {
        if (index !== groupIndex) {
          return group;
        }
        return group.filter((_, itemIndex) => itemIndex !== conditionIndex);
      });
      const cleanedFilters = nextFilters.filter(
        (group, index) => group.length > 0 || index === nextFilters.length - 1
      );
      return cleanedFilters.length > 0 ? cleanedFilters : [[]];
    });
  }

  function removeUnionGroup(groupIndex) {
    setUnionFilters((currentValue) => {
      const nextFilters = currentValue.filter((_, index) => index !== groupIndex);
      return nextFilters.length > 0 ? nextFilters : [[]];
    });
  }

  function removeExcludeCondition(conditionIndex) {
    setExcludeFilters((currentValue) =>
      currentValue.filter((_, index) => index !== conditionIndex)
    );
  }

  function buildFiltersPayload() {
    const filtersPayload = {};

    unionFilters.forEach((group, index) => {
      if (group.length === 0) {
        return;
      }
      const groupPayload = {};
      group.forEach((condition) => {
        if (!groupPayload[condition.key]) {
          groupPayload[condition.key] = [];
        }
        groupPayload[condition.key].push(condition.value);
      });
      filtersPayload[`filter-union-${index}`] = groupPayload;
    });

    if (excludeFilters.length > 0) {
      const excludePayload = {};
      excludeFilters.forEach((condition) => {
        if (!excludePayload[condition.key]) {
          excludePayload[condition.key] = [];
        }
        excludePayload[condition.key].push(condition.value);
      });
      filtersPayload["filter-exclude"] = excludePayload;
    }

    return filtersPayload;
  }

  async function handlePreviewRefinement(filters, defaultName) {
    setErrors([]);
    setSuccessMessage("");
    setIsPreviewing(true);

    try {
      const response = await previewProjectFilters(context.api, projectId, filters);
      setPreview({
        defaultName,
        filters,
        number_documents: response.number_documents,
      });
    } catch (error) {
      setPreview(null);
      setErrors(error.messages ?? [error.message]);
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleCreateRefinement(refinementName) {
    if (!preview) {
      return;
    }

    setErrors([]);
    setIsCreatingRefinement(true);

    try {
      const response = await createProjectRefinement(
        context.api,
        projectId,
        refinementName,
        preview.filters
      );
      window.location.assign(response.url);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
      setIsCreatingRefinement(false);
    }
  }

  async function handleDeleteRefinement(refinementId) {
    setErrors([]);
    setSuccessMessage("");

    try {
      await deleteProjectRefinement(context.api, projectId, refinementId);
      setOverview((currentValue) => ({
        ...currentValue,
        refinements: currentValue.refinements.filter(
          (refinement) => refinement.id !== refinementId
        ),
      }));
      setSuccessMessage("Refinement removed.");
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    }
  }

  async function handleGenerateSummary(clusterId) {
    setErrors([]);
    setGeneratingClusterId(clusterId);

    try {
      const response = await generateProjectClusterSummary(
        context.api,
        projectId,
        clusterId
      );
      setOverview((currentValue) => ({
        ...currentValue,
        cluster_summaries: currentValue.cluster_summaries.map((summary) =>
          summary.cluster_id === clusterId ? response.cluster : summary
        ),
      }));
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setGeneratingClusterId(null);
    }
  }

  async function handleAskTopDocs() {
    setErrors([]);
    setIsStartingTopDocs(true);

    try {
      const response = await askTopDocuments(context.api, projectId);
      window.location.assign(response.urls.rag);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
      setIsStartingTopDocs(false);
    }
  }

  async function handleDeleteProject() {
    if (!deleteModalProject) {
      return;
    }

    setErrors([]);
    setIsDeletingProject(true);

    try {
      await deleteProject(context.api, deleteModalProject.id);
      window.location.assign(context.urls.search);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
      setIsDeletingProject(false);
    }
  }

  const addDisabled = (() => {
    if (!currentFilterType) {
      return true;
    }
    const normalizedDraft = normalizeDraftValue(currentFilterType, draft.value);
    return !normalizedDraft.value || Boolean(normalizedDraft.error);
  })();

  return (
    <section className="container py-5 mt-5">
      <div className="pt-4">
        <h1 className="text-center col-12 mb-5 text-dark">
          <i className="text-dark fa-solid fa-book-open-reader me-2" />
          Project: {overview?.project?.name || projectId}
        </h1>
      </div>

      {overview?.filters ? (
        <div className="row text-center mb-3">
          <div className="alert alert-light border">
            Refinements used: {overview.filters.refinement_count}/
            {overview.filters.refinement_limit}
          </div>
        </div>
      ) : null}

      {successMessage ? (
        <div className="alert alert-success" role="status">
          {successMessage}
        </div>
      ) : null}

      {errors.map((errorMessage) => (
        <div className="alert alert-danger" key={errorMessage} role="alert">
          {errorMessage}
        </div>
      ))}

      {isLoading ? <p>Loading project overview...</p> : null}

      {!isLoading && overview ? (
        <>
          <div className="container">
            <div className="row">
              <div className="mx-auto col-lg-8 col-md-12 col-sm-12">
                <hr />
                <div className="fw-bold fs-3">Details</div>
                <table className="table">
                  <tbody>
                    <tr>
                      <th scope="row">Creation date</th>
                      <td>{formatDate(overview.project.creation_date)}</td>
                    </tr>
                    <tr>
                      <th scope="row">Query</th>
                      <td>{overview.project.query}</td>
                    </tr>
                    {overview.project.natural_language_query ? (
                      <tr>
                        <th scope="row">Natural language query</th>
                        <td>{overview.project.natural_language_query}</td>
                      </tr>
                    ) : null}
                    <tr>
                      <th scope="row">Range date project</th>
                      <td>
                        <div>From: {formatDate(overview.project.range_begin_date)}</div>
                        <div>To: {formatDate(overview.project.range_end_date)}</div>
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">Project sources</th>
                      <td>{overview.project.selected_indices.join(", ") || "-"}</td>
                    </tr>
                    <tr>
                      <th scope="row">
                        {overview.project.is_finish
                          ? "Number of Documents"
                          : "Estimated Documents"}
                      </th>
                      <td>{overview.project.processed_documents}</td>
                    </tr>
                    <tr>
                      <th scope="row">Status</th>
                      <td>{overview.project.step_label}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="d-grid gap-2 col-4 mx-auto align-self-start mt-4">
                <button
                  className="btn btn-primary btn-lg mt-2"
                  disabled={isPreviewing}
                  onClick={() =>
                    handlePreviewRefinement({}, `${overview.project.name} - All Documents`)
                  }
                  type="button"
                >
                  <i className="fa-regular fa-file-alt me-2" />
                  See All Documents
                </button>
                <button
                  className="btn btn-secondary btn-lg mt-2 mb-5"
                  disabled={isStartingTopDocs}
                  onClick={handleAskTopDocs}
                  type="button"
                >
                  <i className="fa-regular fa-comment me-2" />
                  {isStartingTopDocs
                    ? "Preparing Top Documents..."
                    : "Ask to top 10 relevant Documents"}
                </button>
              </div>
            </div>

            {overview.project.can_delete ? (
              <div className="row">
                <div className="mx-auto col-lg-8 col-md-12 col-sm-12">
                  <div className="fw-bold fs-3 mb-2 mt-3">Management</div>
                  <div className="row">
                    <div className="d-grid gap-2 col-4 mx-auto">
                      <button
                        className="btn btn-danger mt-2 mb-5 text-white"
                        onClick={() => setDeleteModalProject(overview.project)}
                        type="button"
                      >
                        <i className="fa-regular fa-trash-can me-2" />
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          {overview.project.is_finish && overview.no_clusters ? (
            <div className="row text-center mt-5 mb-5">
              <div className="fs-5 alert alert-info">
                <strong>
                  The project documents could not be classified into clusters.
                </strong>
              </div>
            </div>
          ) : null}

          {overview.project.is_finish && !overview.no_clusters ? (
            <>
              <div className="container my-2">
                <div className="text-center">
                  <div className="fw-bold fs-3 d-inline-block me-3 mt-5">
                    Clusters plot
                  </div>
                </div>
              </div>
              <div className="d-flex justify-content-center mt-3 mb-5">
                <div className="d-flex container">
                  <BokehPlot plot={overview.plot} />
                </div>
              </div>
            </>
          ) : null}

          {!overview.project.is_finish && overview.project.is_running ? (
            <div className="row text-center mt-5 mb-5">
              <div className="fs-5 alert alert-info">
                <strong>
                  {overview.project.progress.message ||
                    "Project documents are still being processed."}
                </strong>
              </div>
            </div>
          ) : null}

          {overview.project.is_finish ? (
            <ClusterSummaryTable
              clusterSummaries={overview.cluster_summaries}
              generatingClusterId={generatingClusterId}
              onGenerateSummary={handleGenerateSummary}
            />
          ) : null}

          <div className="container">
            <div className="row">
              <div className="col-12">
                <div className="row">
                  <h3 className="text-center">Refine search</h3>
                </div>
                <div className="row my-2 g-3 align-items-start">
                  <div className="col-lg-3">
                    <label className="form-label" htmlFor="project-filter-type">
                      Filter type
                    </label>
                    <select
                      className="form-select form-select-lg"
                      id="project-filter-type"
                      onChange={(event) => handleTypeChange(event.target.value)}
                      value={currentFilterType?.value || draft.type}
                    >
                      {filterTypes.map((filterType) => (
                        <option key={filterType.value} value={filterType.value}>
                          {filterType.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="col-lg-6">
                    <label className="form-label" htmlFor="project-filter-value">
                      Value
                    </label>
                    {currentFilterType?.input_kind === "select" ? (
                      <select
                        className="form-select form-select-lg"
                        id="project-filter-value"
                        onChange={(event) =>
                          setDraft((currentValue) => ({
                            ...currentValue,
                            value: event.target.value,
                          }))
                        }
                        value={draft.value}
                      >
                        {(currentFilterType.options ?? []).map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    ) : currentFilterType?.input_kind === "datalist" ? (
                      <>
                        <input
                          className="form-control form-control-lg"
                          id="project-filter-value"
                          list="project-filter-options"
                          onChange={(event) => {
                            setDraft((currentValue) => ({
                              ...currentValue,
                              value: event.target.value,
                            }));
                            setYearRangeError("");
                          }}
                          placeholder={currentFilterType.placeholder}
                          type="text"
                          value={draft.value}
                        />
                        <datalist id="project-filter-options">
                          {(currentFilterType.options ?? []).map((option) => (
                            <option key={option.value} value={option.value} />
                          ))}
                        </datalist>
                      </>
                    ) : (
                      <input
                        className="form-control form-control-lg"
                        id="project-filter-value"
                        onChange={(event) => {
                          setDraft((currentValue) => ({
                            ...currentValue,
                            value: event.target.value,
                          }));
                          setYearRangeError("");
                        }}
                        placeholder={currentFilterType?.placeholder || "Criteria"}
                        type="text"
                        value={draft.value}
                      />
                    )}
                    {yearRangeError ? (
                      <small className="text-danger">{yearRangeError}</small>
                    ) : null}
                  </div>

                  <div className="col-lg-3 d-flex justify-content-around pt-lg-4 mt-lg-2">
                    <button
                      className="btn-lg btn btn-success"
                      disabled={addDisabled}
                      onClick={() => handleAddCondition("union")}
                      type="button"
                    >
                      Add (And)
                    </button>
                    <button
                      className="btn-lg btn btn-secondary"
                      disabled={addDisabled}
                      onClick={() => handleAddCondition("exclude")}
                      type="button"
                    >
                      Exclude (Not)
                    </button>
                  </div>
                </div>

                <div className="row mt-4">
                  {unionFilters.map((group, groupIndex) => (
                    <div className="py-3 col-12" key={`group-${groupIndex}`}>
                      <div className="card border bg-info border-secondary border-3 rounded">
                        <div className="card-body">
                          <div className="d-flex justify-content-between align-items-center mb-3">
                            <h4 className="mb-0">Filter {groupIndex + 1}</h4>
                            {unionFilters.length > 1 || group.length > 0 ? (
                              <button
                                className="btn btn-danger text-white"
                                onClick={() => removeUnionGroup(groupIndex)}
                                type="button"
                              >
                                X
                              </button>
                            ) : null}
                          </div>
                          <div>
                            {group.length > 0 ? (
                              group.map((condition, conditionIndex) => (
                                <FilterConditionButton
                                  key={`${condition.key}-${condition.value}-${conditionIndex}`}
                                  label={condition.label}
                                  onRemove={() =>
                                    removeUnionCondition(groupIndex, conditionIndex)
                                  }
                                />
                              ))
                            ) : (
                              <p className="mb-0 text-muted">
                                Add conditions to build this filter.
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                      {groupIndex < unionFilters.length - 1 ? (
                        <div className="fs-3 d-flex mt-2">
                          <span className="badge text-bg-success rounded-pill align-self-center">
                            OR
                          </span>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>

                <div className="row">
                  <div className="mx-auto col-11">
                    <p className="d-flex justify-content-center">
                      <button
                        className="btn btn-outline-success btn-lg my-2"
                        onClick={handleCreateUnionFilter}
                        type="button"
                      >
                        Create Filter (Union)
                      </button>
                    </p>
                  </div>
                </div>

                {excludeFilters.length > 0 ? (
                  <div className="mt-3">
                    <div className="fs-3 d-flex">
                      <span
                        className="badge text-bg-danger rounded-pill align-self-center text-white"
                      >
                        AND NOT
                      </span>
                    </div>
                    <div className="mt-2">
                      {excludeFilters.map((condition, conditionIndex) => (
                        <FilterConditionButton
                          key={`${condition.key}-${condition.value}-${conditionIndex}`}
                          label={condition.label}
                          onRemove={() => removeExcludeCondition(conditionIndex)}
                        />
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="container">
            <div className="row">
              <div className="mx-auto col-11">
                <p className="d-flex justify-content-end">
                  <button
                    className="btn btn-primary btn-lg mt-2 mb-5"
                    disabled={isPreviewing}
                    onClick={() =>
                      handlePreviewRefinement(
                        buildFiltersPayload(),
                        `${overview.project.name} refinement`
                      )
                    }
                    type="button"
                  >
                    {isPreviewing ? "Previewing..." : "Generate"}
                  </button>
                </p>
              </div>
            </div>
          </div>

          <RefinementHistory
            onDelete={handleDeleteRefinement}
            refinements={overview.refinements}
          />
        </>
      ) : null}

      <RefinementConfirmationModal
        initialName={preview?.defaultName}
        isSubmitting={isCreatingRefinement}
        onCancel={() => {
          setPreview(null);
          setIsCreatingRefinement(false);
        }}
        onConfirm={handleCreateRefinement}
        preview={preview}
      />
      <DeleteProjectModal
        isSubmitting={isDeletingProject}
        onCancel={() => {
          setDeleteModalProject(null);
          setIsDeletingProject(false);
        }}
        onConfirm={handleDeleteProject}
        project={deleteModalProject}
      />
    </section>
  );
}

export default Project;
