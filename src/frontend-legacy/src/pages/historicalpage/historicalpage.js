import { useCallback, useEffect, useState } from "react";

import {
  deleteAllFinishedProjects,
  deleteProject,
  fetchHistoricalProjects,
} from "../../libs/projects";

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return value;
}

function DeleteProjectModal({ isSubmitting, project, onCancel, onConfirm }) {
  if (!project) {
    return null;
  }

  return (
    <>
      <div className="modal-backdrop fade show" />
      <div
        aria-labelledby="historical-delete-title"
        aria-modal="true"
        className="modal d-block"
        role="dialog"
        tabIndex="-1"
      >
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title fs-5" id="historical-delete-title">
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
              <div className="ms-3 mb-3">
                Query: {project.query || "No query"}
              </div>
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

function DeleteAllModal({ isSubmitting, onCancel, onConfirm, show }) {
  if (!show) {
    return null;
  }

  return (
    <>
      <div className="modal-backdrop fade show" />
      <div
        aria-labelledby="historical-delete-all-title"
        aria-modal="true"
        className="modal d-block"
        role="dialog"
        tabIndex="-1"
      >
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title fs-5" id="historical-delete-all-title">
                Delete All Finished Projects
              </h2>
              <button
                aria-label="Close"
                className="btn-close"
                onClick={onCancel}
                type="button"
              />
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete all finished projects?</p>
              <p>All finished projects will be permanently removed.</p>
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
                {isSubmitting ? "Deleting..." : "Delete all finished"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function HistoricalProjectRow({ isActionBusy, onDelete, project }) {
  return (
    <article className="card shadow-sm border-0 mb-4">
      <div className="card-body">
        <div className="row align-items-center g-3">
          <div className="col-lg-4">
            <a className="fw-bold text-decoration-none" href={project.project_url}>
              {project.name}
            </a>
          </div>
          <div className="col-lg-4">
            <div className="text-muted small">Query</div>
            <div>{project.query || "No query"}</div>
          </div>
          <div className="col-lg-2 text-lg-center">
            <div className="text-muted small">Documents</div>
            <div>{project.processed_documents}</div>
          </div>
          <div className="col-lg-2 text-lg-end">
            {project.can_delete ? (
              <button
                className="btn btn-danger btn-sm"
                disabled={isActionBusy}
                onClick={() => onDelete(project)}
                type="button"
              >
                Delete
              </button>
            ) : (
              <span className="badge text-bg-secondary">Shared</span>
            )}
          </div>
        </div>

        <div className="row text-muted small mt-4 g-3">
          <div className="col-md-3">
            <div className="fw-semibold">Created on</div>
            <div>{formatDate(project.creation_date)}</div>
          </div>
          <div className="col-md-3">
            <div className="fw-semibold">Decision date range</div>
            <div>from: {formatDate(project.range_begin_date)}</div>
            <div>to: {formatDate(project.range_end_date)}</div>
          </div>
          <div className="col-md-3">
            <div className="fw-semibold">Sources</div>
            <div>{project.selected_indices.join(", ") || "-"}</div>
          </div>
          <div className="col-md-3">
            <div className="fw-semibold">Best DBCV</div>
            <div>{project.best_dbcv?.toFixed(3) ?? "0.000"}</div>
          </div>
        </div>
      </div>
    </article>
  );
}

function HistoricalPage({ context }) {
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);
  const [errors, setErrors] = useState([]);
  const [formState, setFormState] = useState({
    search: "",
    sortType: "more_documents_first",
  });
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDeletingAll, setIsDeletingAll] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [projects, setProjects] = useState([]);
  const [queryFilter, setQueryFilter] = useState("");
  const [selectedProject, setSelectedProject] = useState(null);
  const [successMessage, setSuccessMessage] = useState("");
  const [busyProjectId, setBusyProjectId] = useState(null);

  const loadProjects = useCallback(
    async (nextSearch = formState.search, nextSortType = formState.sortType) => {
      setErrors([]);
      try {
        const response = await fetchHistoricalProjects(context.api, {
          search: nextSearch,
          sortType: nextSortType,
        });
        setProjects(response.projects ?? []);
        setQueryFilter(response.query_filter ?? "");
        setFormState({
          search: nextSearch,
          sortType: response.sort_type ?? nextSortType,
        });
      } catch (error) {
        setErrors(error.messages ?? [error.message]);
      } finally {
        setIsLoading(false);
      }
    },
    [context.api, formState.search, formState.sortType]
  );

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSuccessMessage("");
    setIsLoading(true);
    await loadProjects(formState.search, formState.sortType);
  }

  async function handleClearFilters() {
    setSuccessMessage("");
    setFormState({
      search: "",
      sortType: "more_documents_first",
    });
    setIsLoading(true);
    await loadProjects("", "more_documents_first");
  }

  async function handleDeleteProject() {
    if (!selectedProject) {
      return;
    }

    setErrors([]);
    setSuccessMessage("");
    setIsDeleting(true);

    try {
      await deleteProject(context.api, selectedProject.id);
      setProjects((currentValue) =>
        currentValue.filter((project) => project.id !== selectedProject.id)
      );
      setSuccessMessage("Project deleted.");
      setSelectedProject(null);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setIsDeleting(false);
      setBusyProjectId(null);
    }
  }

  async function handleDeleteAll() {
    setErrors([]);
    setSuccessMessage("");
    setIsDeletingAll(true);

    try {
      const response = await deleteAllFinishedProjects(context.api);
      await loadProjects(formState.search, formState.sortType);
      setSuccessMessage(`Deleted ${response.deleted_count ?? 0} finished projects.`);
      setDeleteAllOpen(false);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setIsDeletingAll(false);
    }
  }

  return (
    <section className="container py-5 mt-5">
      <div className="pt-4">
        <h1 className="text-center mb-4 text-dark">
          <i className="fa-regular fa-rectangle-list me-3" />
          Historical Search
        </h1>
      </div>

      <form className="card shadow-sm border-0 mb-4" onSubmit={handleSubmit}>
        <div className="card-body row g-3 align-items-end">
          <div className="col-lg-5">
            <label className="form-label" htmlFor="historical-search-input">
              Search
            </label>
            <input
              className="form-control"
              id="historical-search-input"
              onChange={(event) =>
                setFormState((currentValue) => ({
                  ...currentValue,
                  search: event.target.value,
                }))
              }
              placeholder="Historical search keywords"
              type="text"
              value={formState.search}
            />
          </div>
          <div className="col-lg-4">
            <label className="form-label" htmlFor="historical-sort-select">
              Sorting type
            </label>
            <select
              className="form-select"
              id="historical-sort-select"
              onChange={(event) =>
                setFormState((currentValue) => ({
                  ...currentValue,
                  sortType: event.target.value,
                }))
              }
              value={formState.sortType}
            >
              <option value="more_documents_first">More Documents first</option>
              <option value="less_documents_first">Less Documents first</option>
            </select>
          </div>
          <div className="col-lg-1 d-grid">
            <button className="btn btn-primary" disabled={isLoading} type="submit">
              Search
            </button>
          </div>
          <div className="col-lg-1 d-grid">
            <button
              className="btn btn-dark"
              disabled={isLoading}
              onClick={handleClearFilters}
              type="button"
            >
              Clear
            </button>
          </div>
        </div>
      </form>

      {queryFilter ? (
        <h2 className="h5 mb-3">
          <span className="badge text-bg-info">filter by keywords: {queryFilter}</span>
        </h2>
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

      {isLoading ? <p>Loading projects...</p> : null}

      {!isLoading && projects.length === 0 ? (
        <div className="alert alert-light border" role="status">
          No finished projects were found.
        </div>
      ) : null}

      {projects.map((project) => (
        <HistoricalProjectRow
          isActionBusy={busyProjectId === project.id}
          key={project.id}
          onDelete={(selectedValue) => {
            setBusyProjectId(selectedValue.id);
            setSelectedProject(selectedValue);
          }}
          project={project}
        />
      ))}

      {projects.length > 0 ? (
        <div className="d-flex justify-content-end">
          <button
            className="btn btn-danger"
            onClick={() => setDeleteAllOpen(true)}
            type="button"
          >
            Delete all finished projects
          </button>
        </div>
      ) : null}

      <DeleteProjectModal
        isSubmitting={isDeleting}
        onCancel={() => {
          setSelectedProject(null);
          setBusyProjectId(null);
        }}
        onConfirm={handleDeleteProject}
        project={selectedProject}
      />
      <DeleteAllModal
        isSubmitting={isDeletingAll}
        onCancel={() => setDeleteAllOpen(false)}
        onConfirm={handleDeleteAll}
        show={deleteAllOpen}
      />
    </section>
  );
}

export default HistoricalPage;
