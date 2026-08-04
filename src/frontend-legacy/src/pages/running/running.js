import { useCallback, useEffect, useState } from "react";

import {
  deleteProject,
  fetchRunningProjects,
  restartRunningProject,
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
        aria-labelledby="running-delete-title"
        aria-modal="true"
        className="modal d-block"
        role="dialog"
        tabIndex="-1"
      >
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title fs-5" id="running-delete-title">
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
              <div className="ms-3">
                Total documents: {project.total_documents}
              </div>
              <div className="ms-3">Creation date: {project.creation_date}</div>
              <div className="ms-3 mb-3">Status: {project.step_label}</div>
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

function RunningProjectRow({ isActionBusy, onDelete, onRestart, project }) {
  const progress = project.progress ?? {};

  return (
    <article className="card shadow-sm border-0 mb-4">
      <div className="card-body">
        <div className="row align-items-center g-3">
          <div className="col-lg-3">
            {project.can_open_project ? (
              <a className="fw-bold text-decoration-none" href={project.project_url}>
                {project.name}
              </a>
            ) : (
              <span className="fw-bold">{project.name}</span>
            )}
          </div>
          <div className="col-lg-3">
            <div className="text-muted small">Query</div>
            <div>{project.query || "No query"}</div>
          </div>
          <div className="col-lg-2">
            <div className="text-muted small">Status</div>
            <div>{project.step_label}</div>
          </div>
          <div className="col-lg-3">
            <div className="text-muted small">Progress</div>
            {progress.kind === "progress" ? (
              <>
                <div className="d-flex justify-content-between">
                  <span>{progress.label}</span>
                  <span>{progress.percentage}%</span>
                </div>
                <div className="progress" style={{ height: "24px" }}>
                  <div
                    aria-valuemax="100"
                    aria-valuemin="0"
                    aria-valuenow={progress.percentage}
                    className="progress-bar"
                    role="progressbar"
                    style={{ width: `${progress.percentage}%` }}
                  >
                    {progress.message}
                  </div>
                </div>
              </>
            ) : (
              <span>{progress.message ?? progress.label ?? "Working"}</span>
            )}
          </div>
          <div className="col-lg-1 text-lg-end">
            <div className="btn-group">
              {project.can_restart ? (
                <button
                  className="btn btn-outline-primary btn-sm"
                  disabled={isActionBusy}
                  onClick={() => onRestart(project)}
                  type="button"
                >
                  Restart
                </button>
              ) : null}
              {project.can_delete ? (
                <button
                  className="btn btn-danger btn-sm"
                  disabled={isActionBusy}
                  onClick={() => onDelete(project)}
                  type="button"
                >
                  Delete
                </button>
              ) : null}
            </div>
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

function Running({ context }) {
  const [errors, setErrors] = useState([]);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [successMessage, setSuccessMessage] = useState("");
  const [busyProjectId, setBusyProjectId] = useState(null);

  const loadProjects = useCallback(async () => {
    setErrors([]);
    try {
      const response = await fetchRunningProjects(context.api);
      setProjects(response.projects ?? []);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setIsLoading(false);
    }
  }, [context.api]);

  useEffect(() => {
    loadProjects();
    const intervalId = window.setInterval(() => {
      loadProjects();
    }, 10000);

    return () => window.clearInterval(intervalId);
  }, [loadProjects]);

  async function handleRestart(project) {
    setErrors([]);
    setSuccessMessage("");
    setBusyProjectId(project.id);

    try {
      const response = await restartRunningProject(context.api, project.id);
      setSuccessMessage(response.detail ?? "Project restart requested.");
      await loadProjects();
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setBusyProjectId(null);
    }
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
    }
  }

  return (
    <section className="container py-5 mt-5">
      <div className="pt-4">
        <h1 className="text-center mb-4 text-dark">
          <i className="fa-solid fa-gears me-3" />
          Project Status
        </h1>
      </div>

      <div className="d-flex justify-content-end mb-4">
        <button className="btn btn-primary" onClick={loadProjects} type="button">
          Check status
        </button>
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

      {isLoading ? <p>Loading projects...</p> : null}

      {!isLoading && projects.length === 0 ? (
        <div className="alert alert-light border" role="status">
          No running projects were found.
        </div>
      ) : null}

      {projects.map((project) => (
        <RunningProjectRow
          isActionBusy={busyProjectId === project.id}
          key={project.id}
          onDelete={setSelectedProject}
          onRestart={handleRestart}
          project={project}
        />
      ))}

      <DeleteProjectModal
        isSubmitting={isDeleting}
        onCancel={() => setSelectedProject(null)}
        onConfirm={handleDeleteProject}
        project={selectedProject}
      />
    </section>
  );
}

export default Running;
