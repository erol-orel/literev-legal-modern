import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  activateTableSelectionIteration,
  askSelectedTableDocuments,
  deleteTableSelectionIteration,
  exportTableSelection,
  fetchTableSelectionState,
  iterateTableSelection,
  resetTableSelection,
  setAllTableSelection,
  updateTableSelection,
} from "../../libs/table_selection";

function buildTableSelectionPath(basePath, projectId, refinementId, iterationId, page, orderBy) {
  if (!iterationId) {
    return `${basePath}${projectId}/${refinementId}/`;
  }

  return `${basePath}${projectId}/${refinementId}/${iterationId}/page=${page}/order_by=${orderBy}/`;
}

function normalizePath(pathname) {
  if (!pathname) {
    return "/";
  }
  return pathname.endsWith("/") ? pathname : `${pathname}/`;
}

function parseTableSelectionPath(pathname) {
  const detailMatch = pathname.match(
    /^\/tableselect\/(\d+)\/(\d+)\/(\d+)\/page=(\d+)\/order_by=([^/]+)\/?$/
  );
  if (detailMatch) {
    return {
      iterationId: Number(detailMatch[3]),
      orderBy: decodeURIComponent(detailMatch[5]),
      page: Number(detailMatch[4]),
      projectId: detailMatch[1],
      refinementId: detailMatch[2],
    };
  }

  const defaultMatch = pathname.match(/^\/tableselect\/(\d+)\/(\d+)\/?$/);
  if (defaultMatch) {
    return {
      iterationId: null,
      orderBy: "es_score",
      page: 1,
      projectId: defaultMatch[1],
      refinementId: defaultMatch[2],
    };
  }

  return {
    iterationId: null,
    orderBy: "es_score",
    page: 1,
    projectId: null,
    refinementId: null,
  };
}

function initialSelectionForRows(rows) {
  return Object.fromEntries(
    rows.map((row) => {
      let value = "maybe";
      if (row.is_check === true) {
        value = "yes";
      } else if (row.is_check === false) {
        value = "no";
      }
      return [row.id, value];
    })
  );
}

function selectionPayloadFromState(selectionState) {
  const selectedDocuments = [];
  const deselectedDocuments = [];
  const maybeDocuments = [];

  Object.entries(selectionState).forEach(([rowId, value]) => {
    const numericId = Number(rowId);
    if (value === "yes") {
      selectedDocuments.push(numericId);
    } else if (value === "no") {
      deselectedDocuments.push(numericId);
    } else {
      maybeDocuments.push(numericId);
    }
  });

  return {
    deselected_documents: deselectedDocuments,
    maybe_documents: maybeDocuments,
    selected_documents: selectedDocuments,
  };
}

function filenameFromDisposition(disposition) {
  if (!disposition) {
    return "selected_documents_literev.csv";
  }

  const match = disposition.match(/filename=([^;]+)/i);
  if (!match) {
    return "selected_documents_literev.csv";
  }

  return match[1].replaceAll('"', "").trim();
}

function FilterSummary({ filters }) {
  if (!filters?.union_sets_html && !filters?.excluded_set_html) {
    return null;
  }

  return (
    <table className="table mb-0">
      <tbody>
        {filters.union_sets_html ? (
          <tr>
            <th scope="row">Refinement criteria</th>
            <td dangerouslySetInnerHTML={{ __html: filters.union_sets_html }} />
          </tr>
        ) : null}
        {filters.excluded_set_html ? (
          <tr>
            <th scope="row">Excluded set</th>
            <td dangerouslySetInnerHTML={{ __html: filters.excluded_set_html }} />
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}

function IterationTrail({ activeOrderBy, iterations, onActivate, onDelete }) {
  if (!iterations?.length) {
    return null;
  }

  return (
    <div className="container mb-4">
      {iterations.map((iteration) => {
        const canDelete = !iteration.is_parent && !iteration.is_root;

        return (
          <span className="me-3 d-inline-flex align-items-center" key={iteration.id}>
            {iteration.is_active ? (
              <span className="btn btn-secondary mb-3">
                Current: {iteration.name}
              </span>
            ) : (
              <button
                className="btn btn-outline-secondary mb-3"
                onClick={() => onActivate(iteration.id, activeOrderBy)}
                type="button"
              >
                {iteration.name}
              </button>
            )}
            {canDelete ? (
              <button
                className="btn btn-outline-danger ms-2 mb-3"
                onClick={() => onDelete(iteration.id, activeOrderBy)}
                type="button"
              >
                X
              </button>
            ) : null}
            {iteration.is_parent ? (
              <span className="fs-3 text-secondary ms-2 mb-3">
                <i className="fa-solid fa-chevron-right" />
              </span>
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

function TableSelectionRow({
  hasEsScores,
  hasHdbscanScores,
  row,
  selectionValue,
  onChange,
}) {
  return (
    <article className="card shadow-sm border-0 mb-4">
      <div className="card-body">
        <div className="row g-3">
          <div className="col-lg-2">
            <fieldset>
              <legend className="visually-hidden">Selection</legend>
              <div className="btn-group-vertical w-100" role="group">
                <input
                  checked={selectionValue === "yes"}
                  className="btn-check"
                  id={`selection-yes-${row.id}`}
                  name={`selection-${row.id}`}
                  onChange={() => onChange(row.id, "yes")}
                  type="radio"
                />
                <label className="btn btn-outline-success mb-2" htmlFor={`selection-yes-${row.id}`}>
                  <i className="fa-solid fa-check me-2" />Yes
                </label>
                <input
                  checked={selectionValue === "maybe"}
                  className="btn-check"
                  id={`selection-maybe-${row.id}`}
                  name={`selection-${row.id}`}
                  onChange={() => onChange(row.id, "maybe")}
                  type="radio"
                />
                <label
                  className="btn btn-outline-secondary mb-2"
                  htmlFor={`selection-maybe-${row.id}`}
                >
                  <i className="fa-solid fa-question me-2" />Maybe
                </label>
                <input
                  checked={selectionValue === "no"}
                  className="btn-check"
                  id={`selection-no-${row.id}`}
                  name={`selection-${row.id}`}
                  onChange={() => onChange(row.id, "no")}
                  type="radio"
                />
                <label className="btn btn-outline-danger" htmlFor={`selection-no-${row.id}`}>
                  <i className="fa-solid fa-xmark me-2" />No
                </label>
              </div>
            </fieldset>
          </div>
          <div className="col-lg-10">
            <div
              className={`d-flex ${
                hasEsScores ? "justify-content-between" : "justify-content-end"
              }`}
            >
              {hasEsScores && row.es_score !== undefined ? (
                <div className="fs-5 align-self-center">
                  <span className="badge bg-score-query text-dark">
                    Query relevance score: {Number(row.es_score).toFixed(2)}
                  </span>
                </div>
              ) : null}
              {row.is_initial === false ? (
                <div className="fs-5 align-self-center">
                  <span className="badge text-bg-dark">
                    <i className="fa-solid fa-file-circle-plus me-2" />New neighbor document
                  </span>
                </div>
              ) : null}
              <h3>
                <span className="badge text-bg-dark">
                  <a className="text-white" href={row.content_url}>
                    {row.procedure_type || "Open document"}
                  </a>
                </span>
              </h3>
            </div>
            <div className="mt-3 text-start mb-3">
              <div>
                <b>{row.decision_type || "-"}</b>, du {row.decision_date || "-"}{" "}
                <b>Result:</b> {row.result || "-"}
              </div>
            </div>
            <div className="mb-3">
              <b>Normes:</b> {row.standards || "-"}
            </div>
            <div className="mb-3">
              <b>Extraits:</b>{" "}
              <span dangerouslySetInnerHTML={{ __html: `${row.sample_document || ""} ...` }} />
            </div>
            {hasHdbscanScores ? (
              <div className="text-center fs-5 overflow-auto">
                <span
                  className="badge text-dark overflow-auto me-2"
                  style={{ backgroundColor: `${row.color || "#adb5bd"}80` }}
                >
                  {row.topic}
                </span>
                <span className="badge bg-light text-dark">
                  Topic score : {Number(row.hdbscan_score || 0).toFixed(1)} %
                </span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}

function TableSelection({ context }) {
  const location = useLocation();
  const navigate = useNavigate();
  const routeState = useMemo(
    () => parseTableSelectionPath(location.pathname),
    [location.pathname]
  );
  const projectId = routeState.projectId;
  const refinementId = routeState.refinementId;
  const numericPage = routeState.page;
  const numericIterationId = routeState.iterationId;
  const requestedOrderBy = routeState.orderBy;
  const [busyAction, setBusyAction] = useState("");
  const [errors, setErrors] = useState([]);
  const [payload, setPayload] = useState(null);
  const [selectionState, setSelectionState] = useState({});
  const [sortSelection, setSortSelection] = useState("es_score");
  const [successMessage, setSuccessMessage] = useState("");

  const routeBase = context.urls.tableselectBase || "/tableselect/";

  const currentSelectionPayload = useMemo(
    () => selectionPayloadFromState(selectionState),
    [selectionState]
  );

  const loadState = useCallback(async () => {
    if (!projectId || !refinementId) {
      setErrors(["Invalid table-selection route."]);
      return;
    }

    setErrors([]);

    try {
      const response = await fetchTableSelectionState(context.api, {
        projectId,
        refinementId,
        iterationId: numericIterationId,
        orderBy: requestedOrderBy,
        page: Number.isFinite(numericPage) ? numericPage : 1,
      });

      if (
        response.canonical_url &&
        normalizePath(response.canonical_url) !== normalizePath(location.pathname)
      ) {
        navigate(response.canonical_url, { replace: true });
        return;
      }

      setPayload(response);
      setSortSelection(response.table?.sort_by || "es_score");
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    }
  }, [
    context.api,
    projectId,
    refinementId,
    numericIterationId,
    numericPage,
    requestedOrderBy,
    location.pathname,
    navigate,
  ]);

  useEffect(() => {
    loadState();
  }, [loadState]);

  useEffect(() => {
    const rows = payload?.table?.rows ?? [];
    setSelectionState(initialSelectionForRows(rows));
  }, [payload?.table?.rows]);

  useEffect(() => {
    if (payload?.processing_filters) {
      const intervalId = window.setInterval(() => {
        loadState();
      }, 1300);
      return () => window.clearInterval(intervalId);
    }
    return undefined;
  }, [payload?.processing_filters, loadState]);

  useEffect(() => {
    if (payload?.project?.name) {
      document.title = `LiteRev Legal | ${payload.project.name} Results`;
    }
  }, [payload?.project?.name]);

  function setRowSelection(rowId, value) {
    setSelectionState((currentValue) => ({
      ...currentValue,
      [rowId]: value,
    }));
  }

  async function syncCurrentPageSelection() {
    if (!payload?.current_iteration_id) {
      return;
    }

    await updateTableSelection(context.api, {
      iterationId: payload.current_iteration_id,
      projectId,
      refinementId,
      selection: currentSelectionPayload,
    });
  }

  async function handleNavigate(pageNumber, nextOrderBy = sortSelection) {
    setBusyAction("navigate");
    setErrors([]);
    setSuccessMessage("");

    try {
      await syncCurrentPageSelection();
      navigate(
        buildTableSelectionPath(
          routeBase,
          projectId,
          refinementId,
          payload.current_iteration_id,
          pageNumber,
          nextOrderBy
        )
      );
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyAction("");
    }
  }

  async function handleActivateIteration(nextIterationId, nextOrderBy) {
    setBusyAction("activate-iteration");
    setErrors([]);

    try {
      const response = await activateTableSelectionIteration(context.api, {
        iterationId: nextIterationId,
        orderBy: nextOrderBy,
        projectId,
        refinementId,
      });
      navigate(response.url);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyAction("");
    }
  }

  async function handleDeleteIteration(targetIterationId, nextOrderBy) {
    setBusyAction("delete-iteration");
    setErrors([]);
    setSuccessMessage("");

    try {
      const response = await deleteTableSelectionIteration(context.api, {
        iterationId: targetIterationId,
        orderBy: nextOrderBy,
        projectId,
        refinementId,
      });
      setSuccessMessage(response.detail || "Iteration removed.");
      navigate(response.url);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyAction("");
    }
  }

  async function handleCheckAll(mode) {
    setBusyAction(`check-all-${mode}`);
    setErrors([]);
    setSuccessMessage("");

    try {
      const response = await setAllTableSelection(context.api, {
        iterationId: payload?.current_iteration_id,
        mode,
        projectId,
        refinementId,
      });
      setSuccessMessage(response.detail || "Selection updated.");
      await loadState();
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyAction("");
    }
  }

  async function handleIterate() {
    setBusyAction("iterate");
    setErrors([]);
    setSuccessMessage("");

    try {
      const response = await iterateTableSelection(context.api, {
        iterationId: payload?.current_iteration_id,
        projectId,
        refinementId,
        selection: currentSelectionPayload,
      });
      navigate(response.url);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyAction("");
    }
  }

  async function handleReset() {
    setBusyAction("reset");
    setErrors([]);
    setSuccessMessage("");

    try {
      const response = await resetTableSelection(context.api, {
        projectId,
        refinementId,
      });
      navigate(response.url);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyAction("");
    }
  }

  async function handleAskSelected() {
    setBusyAction("ask-selected");
    setErrors([]);

    try {
      const response = await askSelectedTableDocuments(context.api, {
        iterationId: payload?.current_iteration_id,
        projectId,
        refinementId,
        selection: currentSelectionPayload,
      });
      window.location.assign(response.url);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
      setBusyAction("");
    }
  }

  async function handleExport() {
    setBusyAction("export");
    setErrors([]);

    try {
      const response = await exportTableSelection(context.api, {
        iterationId: payload?.current_iteration_id,
        projectId,
        refinementId,
        selection: currentSelectionPayload,
      });
      const objectUrl = window.URL.createObjectURL(response.blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filenameFromDisposition(response.filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyAction("");
    }
  }

  if (!payload) {
    return (
      <section className="container py-5 mt-5">
        <div className="pt-4">
          <h1 className="text-center col-12 mb-5">
            <i className="fa-regular fa-rectangle-list me-3" />
            Results Table
          </h1>
        </div>
        {errors.map((errorMessage) => (
          <div className="alert alert-danger" key={errorMessage} role="alert">
            {errorMessage}
          </div>
        ))}
        {errors.length === 0 ? <p>Loading table selection...</p> : null}
      </section>
    );
  }

  const counts = payload.counts ?? {};
  const project = payload.project ?? {};
  const table = payload.table ?? { rows: [] };
  const rows = table.rows ?? [];

  return (
    <section className="container py-5 mt-5">
      <div className="pt-4">
        <h1 className="text-center col-12 mb-5">
          <i className="fa-regular fa-rectangle-list me-3" />
          Results Table
        </h1>
      </div>

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

      {payload.processing_filters ? (
        <div className="mt-5 d-flex justify-content-center">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Processing new results...</span>
          </div>
          <span className="ms-3 fs-4 text-secondary">
            Processing new results ...
          </span>
        </div>
      ) : (
        <>
          <div className="card shadow-sm border-0 mb-4">
            <div className="card-body">
              <h2 className="fw-bold fs-3">Details</h2>
              <table className="table mb-0">
                <tbody>
                  <tr>
                    <th scope="row">Project name</th>
                    <td>{project.name}</td>
                  </tr>
                  <tr>
                    <th scope="row">Creation date</th>
                    <td>{project.creation_date}</td>
                  </tr>
                  <tr>
                    <th scope="row">Query</th>
                    <td>{project.query}</td>
                  </tr>
                  <tr>
                    <th scope="row">Range date project</th>
                    <td>
                      <div>From: {project.range_begin_date}</div>
                      <div>To: {project.range_end_date}</div>
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">Number of Documents</th>
                    <td>{project.processed_documents}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="card bg-light border-0 mb-4">
            <div className="card-body">
              <div className="row text-center mb-4 mt-1">
                <div className="col-12">
                  Initial documents number in Refinement:{" "}
                  <span className="fw-bold">{counts.initial || 0}</span>
                </div>
              </div>

              <div className="mb-4">
                <FilterSummary filters={payload.filters} />
              </div>

              <div className="row mb-4">
                <div className="col">k neighbour: <span className="fw-bold">10</span></div>
                <div className="col">
                  New documents: <span className="fw-bold">{counts.neighbour || 0}</span>
                </div>
              </div>

              <div className="row align-items-start">
                <div className="col-lg-6">
                  Document checked: <span className="fw-bold">{counts.chosen || 0}</span>
                </div>
                <div className="col-lg-6 text-lg-end">
                  <button
                    className="btn btn-outline-dark me-2 mb-2"
                    disabled={busyAction !== ""}
                    onClick={() => handleCheckAll("yes")}
                    type="button"
                  >
                    Check All to Yes
                  </button>
                  <button
                    className="btn btn-outline-dark mb-2"
                    disabled={busyAction !== ""}
                    onClick={() => handleCheckAll("maybe")}
                    type="button"
                  >
                    Check All to Maybe
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="d-flex justify-content-center flex-wrap gap-3 mb-4">
            <a className="btn btn-dark" href={payload.urls.back_to_filter}>
              Back to filter
            </a>
            {project.can_iterate ? (
              <button
                className="btn btn-secondary"
                disabled={busyAction !== ""}
                onClick={handleIterate}
                type="button"
              >
                Iterate
              </button>
            ) : null}
            <button
              className="btn btn-secondary"
              disabled={busyAction !== ""}
              onClick={handleReset}
              type="button"
            >
              Reset Iterations
            </button>
            <button
              className="btn btn-primary"
              disabled={busyAction !== ""}
              onClick={handleExport}
              type="button"
            >
              Export Selected
            </button>
            <button
              className="btn btn-primary"
              disabled={busyAction !== ""}
              onClick={handleAskSelected}
              type="button"
            >
              Ask Selected
            </button>
          </div>

          <IterationTrail
            activeOrderBy={table.sort_by}
            iterations={payload.iterations}
            onActivate={handleActivateIteration}
            onDelete={handleDeleteIteration}
          />

          <div className="container text-center mt-4 mb-3">
            <div className="row justify-content-center align-items-center">
              <div
                className={
                  "col-lg-4 d-flex align-items-center justify-content-center " +
                  "justify-content-lg-start mb-3 mb-lg-0"
                }
              >
                <label className="form-label me-2 mb-0" htmlFor="tableselect-sort-select">
                  <b className="text-nowrap">Sort by:</b>
                </label>
                <select
                  className="form-select"
                  id="tableselect-sort-select"
                  onChange={(event) => setSortSelection(event.target.value)}
                  value={sortSelection}
                >
                  {(table.sort_options ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <button
                  className="btn btn-primary ms-2"
                  disabled={busyAction !== ""}
                  onClick={() => handleNavigate(1, sortSelection)}
                  type="button"
                >
                  Apply
                </button>
              </div>
              <div className="col-lg-8 text-lg-end">
                page: <span className="fw-bold">{table.current_page}/{table.total_pages}</span>
              </div>
            </div>
          </div>

          <div className="d-flex justify-content-between mb-3">
            <div>
              {table.current_page > 1 ? (
                <button
                  className="btn btn-outline-dark"
                  disabled={busyAction !== ""}
                  onClick={() => handleNavigate(table.current_page - 1, table.sort_by)}
                  type="button"
                >
                  Previous
                </button>
              ) : null}
            </div>
            <div>
              {table.current_page < table.total_pages ? (
                <button
                  className="btn btn-outline-dark"
                  disabled={busyAction !== ""}
                  onClick={() => handleNavigate(table.current_page + 1, table.sort_by)}
                  type="button"
                >
                  Next
                </button>
              ) : null}
            </div>
          </div>

          {rows.map((row) => (
            <TableSelectionRow
              hasEsScores={table.has_es_scores}
              hasHdbscanScores={table.has_hdbscan_scores}
              key={row.id}
              onChange={setRowSelection}
              row={row}
              selectionValue={selectionState[row.id] || "maybe"}
            />
          ))}

          <div className="d-flex justify-content-between mb-4">
            <div>
              {table.current_page > 1 ? (
                <button
                  className="btn btn-outline-dark"
                  disabled={busyAction !== ""}
                  onClick={() => handleNavigate(table.current_page - 1, table.sort_by)}
                  type="button"
                >
                  Previous
                </button>
              ) : null}
            </div>
            <div>
              {table.current_page < table.total_pages ? (
                <button
                  className="btn btn-outline-dark"
                  disabled={busyAction !== ""}
                  onClick={() => handleNavigate(table.current_page + 1, table.sort_by)}
                  type="button"
                >
                  Next
                </button>
              ) : null}
            </div>
          </div>

          <div className="card bg-light border-0 mb-4">
            <div className="card-body text-center">
              Documents checked: <span className="fw-bold">{counts.chosen || 0}</span>
            </div>
          </div>

          <div className="d-flex justify-content-center flex-wrap gap-3 mb-5">
            <a className="btn btn-dark" href={payload.urls.back_to_filter}>
              Back to filter
            </a>
            {project.can_iterate ? (
              <button
                className="btn btn-secondary btn-lg"
                disabled={busyAction !== ""}
                onClick={handleIterate}
                type="button"
              >
                Iterate
              </button>
            ) : null}
            <button
              className="btn btn-secondary btn-lg"
              disabled={busyAction !== ""}
              onClick={handleReset}
              type="button"
            >
              Reset
            </button>
            <button
              className="btn btn-primary btn-lg"
              disabled={busyAction !== ""}
              onClick={handleExport}
              type="button"
            >
              Export Selected
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export default TableSelection;
