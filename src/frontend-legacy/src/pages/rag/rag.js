import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  createRagEntry,
  deleteRagEntry,
  fetchRagContext,
  fetchRagDocuments,
  fetchRagStatus,
} from "../../libs/rag";

const STATUS_CLASS_MAP = {
  completed: "bg-success",
  failed: "bg-danger",
  questioning_documents: "bg-primary",
  generating_scores: "bg-info",
  generating_summary: "bg-primary",
  generating_statistics: "bg-warning",
  tagging_considerations: "bg-info",
};

const INVALID_ANSWERS = [
  "No content available",
  "Error generating response",
  "Réponse non disponible",
];

const SECTION_KEYS = {
  facts: ["Faits", "Mineure-Faits", "Examen des faits"],
  subsumption: [
    "Subsomption",
    "Mineure-Subsomption",
    "Subsommation",
    "Mineure-Subsommation",
    "Analyse juridique (subsomption)",
  ],
  conclusion: ["Conclusion", "Décision finale"],
};

function asText(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join(" ") : "";
  }
  if (typeof value === "string") {
    return value.trim();
  }
  return "";
}

function pickText(sectionAnswers, keys) {
  if (!sectionAnswers) {
    return "";
  }
  for (const key of keys) {
    const text = asText(sectionAnswers[key]);
    if (text) {
      return text;
    }
  }
  return "";
}

function parseSectionAnswers(answerText) {
  try {
    const parsed = JSON.parse(answerText);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const hasAny =
      SECTION_KEYS.facts.some((key) => parsed[key] !== undefined) ||
      SECTION_KEYS.subsumption.some((key) => parsed[key] !== undefined) ||
      SECTION_KEYS.conclusion.some((key) => parsed[key] !== undefined);
    if (!hasAny) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function formatDate(value) {
  if (!value) {
    return "";
  }
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function RAGHistoryRow({ entry, onDelete, projectId }) {
  const statusClass = STATUS_CLASS_MAP[entry.status] || "bg-light text-dark";

  return (
    <tr id={`rag-row-${entry.id}`}>
      <td>
        <span
          className={`badge text-uppercase small history-status-badge ${statusClass}`}
        >
          {entry.status_display || "In progress"}
        </span>
      </td>
      <td>
        <a
          className="text-decoration-none fw-bold"
          href={`/rag/${projectId}/${entry.id}`}
        >
          {entry.query}
        </a>
      </td>
      <td>
        {entry.valid_answer_count} of {entry.num_documents}
      </td>
      <td>{formatDate(entry.created_at)}</td>
      <td>
        <button
          className="btn btn-danger text-white"
          onClick={() => onDelete(entry.id)}
          type="button"
        >
          <i className="fa-regular fa-trash-can" />
        </button>
      </td>
    </tr>
  );
}

function RagAnswerCard({ documentRag }) {
  if (
    !documentRag?.answer ||
    INVALID_ANSWERS.some((snippet) => documentRag.answer.includes(snippet))
  ) {
    return null;
  }

  const sectionAnswers = parseSectionAnswers(documentRag.answer);
  if (!sectionAnswers && documentRag.answer.trim().length === 0) {
    return null;
  }

  const factAnswer = sectionAnswers
    ? pickText(sectionAnswers, SECTION_KEYS.facts)
    : "";
  const subsumptionAnswer = sectionAnswers
    ? pickText(sectionAnswers, SECTION_KEYS.subsumption)
    : "";
  const conclusionAnswer = sectionAnswers
    ? pickText(sectionAnswers, SECTION_KEYS.conclusion)
    : "";

  if (sectionAnswers && !factAnswer && !subsumptionAnswer && !conclusionAnswer) {
    return null;
  }

  return (
    <div className="mb-3">
      <div className="mb-3 d-flex justify-content-between align-items-center">
        <a
          className="fs-5 text-white badge text-bg-dark"
          href={documentRag.document.url_document}
          target="_blank"
          rel="noreferrer"
        >
          {documentRag.document.procedure_type}
        </a>
        {documentRag.confidence_score != null ? (
          <span className="fs-5 badge text-bg-success rounded-pill">
            Confidence Score: {documentRag.confidence_score.toFixed(2)}
          </span>
        ) : null}
      </div>
      <div className="mb-2">
        <b>{documentRag.document.decision_type}</b>, du {documentRag.document.decision_date}
        <b>Result: </b>
        {documentRag.document.result}
      </div>
      {documentRag.document.standards ? (
        <div className="mb-2">
          <b>Normes: </b>
          {documentRag.document.standards}
        </div>
      ) : null}
      {sectionAnswers ? (
        <>
          {factAnswer ? (
            <div className="mb-2">
              <b>En fait: </b>
              {factAnswer}
            </div>
          ) : null}
          {subsumptionAnswer ? (
            <div className="mb-2">
              <b>Subsomption: </b>
              {subsumptionAnswer}
            </div>
          ) : null}
          {conclusionAnswer ? (
            <div className="mb-2">
              <b>Conclusion: </b>
              {conclusionAnswer}
            </div>
          ) : null}
        </>
      ) : (
        <>
          <div className="mb-2">
            <b>Answer: </b>
            {documentRag.answer}
          </div>
          {documentRag.citation ? (
            <div className="mb-2">
              <b>Highlighted in document: </b>
              {documentRag.citation}
            </div>
          ) : null}
        </>
      )}
      <hr />
    </div>
  );
}

function SummarySection({ current }) {
  if (!current || !current.summary_text) {
    return null;
  }

  return (
    <div className="container mb-4 px-4">
      <div className="alert alert-info">
        <p id="general-ans">
          <strong>Résumé :</strong> {current.summary_text}
        </p>
        {current.considerations?.length ? (
          <>
            <strong>Arguments retenus :</strong>
            <ul className="small">
              {current.considerations.map((consideration) => (
                <li key={`${consideration.text}-${consideration.percent}`}>
                  <strong>{consideration.percent}%</strong> {consideration.text}
                  <div>
                    {(consideration.procedure_types || []).map((proc) => (
                      <span
                        className="badge bg-secondary text-white small ms-1"
                        key={`${consideration.text}-${proc}`}
                      >
                        {proc}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </div>
  );
}

function RegleDroitSection({ current }) {
  if (!current?.has_section_ans || !current.summary_text || !current.regle_droit) {
    return null;
  }

  return (
    <div className="container mb-4 px-4">
      <div className="alert alert-info">
        <p id="general-regle">
          <strong>Règle de droit:</strong> {current.regle_droit}
        </p>
      </div>
    </div>
  );
}

function KeyElementsTable({ current }) {
  if (!current?.has_section_ans || !current.summary_text || !current.key_elements?.length) {
    return null;
  }

  return (
    <>
      <h3 className="mb-3">Tableau des éléments clés</h3>
      <table className="table mb-5">
        <thead className="thead-dark">
          <tr>
            <th scope="col">Élément clé</th>
            <th scope="col">Description</th>
            <th scope="col">Références</th>
          </tr>
        </thead>
        <tbody className="table-group-divider">
          {current.key_elements.map((row, index) => (
            <tr key={`key-elements-${index}`}>
              {Object.entries(row).map(([key, value]) => (
                <td key={`${index}-${key}`}>
                  {key === "references" ? (
                    <>
                      {(value || []).map((ref) => (
                        <a
                          className="badge bg-secondary text-white small ms-1"
                          href={`/contentdocument/${ref.id}`}
                          key={`${ref.id}-${ref.procedure_type}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {ref.procedure_type}
                        </a>
                      ))}
                    </>
                  ) : (
                    value
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function LawArticlesTable({ current }) {
  if (!current?.law_articles?.length) {
    return null;
  }

  return (
    <>
      <h3>Tableau des articles de loi</h3>
      <table className="table mb-5">
        <thead className="thead-dark">
          <tr>
            {Object.keys(current.law_articles[0]).map((key) => (
              <th scope="col" key={key}>
                {key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="table-group-divider">
          {current.law_articles.map((row, index) => (
            <tr key={`law-articles-${index}`}>
              {Object.entries(row).map(([key, value]) => (
                <td key={`${index}-${key}`}>
                  {key === "references" ? (
                    <>
                      {(value || []).map((ref) => (
                        <a
                          className="badge bg-secondary text-white small ms-1"
                          href={`/contentdocument/${ref.id}`}
                          key={`${ref.id}-${ref.procedure_type}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {ref.procedure_type}
                        </a>
                      ))}
                    </>
                  ) : (
                    value
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function ClosedStats({ current }) {
  if (!current?.show_closed_stats) {
    return null;
  }

  const counts = current.counts || {};
  const percentages = current.percentages || {};

  return (
    <div className="container mb-4 px-2">
      <div className="card shadow-sm rounded">
        <div className="card-body">
          <h5 className="card-title text-center mb-3">
            État des réponses analysées
          </h5>
          <div
            className="progress"
            style={{ height: "30px", borderRadius: "8px", overflow: "hidden" }}
          >
            <div
              className="progress-bar"
              role="progressbar"
              style={{
                width: `${percentages.oui || 0}%`,
                backgroundColor: "rgba(76, 127, 175, 0.85)",
                color: "#fff",
              }}
              aria-valuenow={percentages.oui || 0}
              aria-valuemin="0"
              aria-valuemax="100"
            >
              Oui {percentages.oui || 0}%
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              style={{
                width: `${percentages.non || 0}%`,
                backgroundColor: "rgb(233, 94, 84)",
                color: "#fff",
              }}
              aria-valuenow={percentages.non || 0}
              aria-valuemin="0"
              aria-valuemax="100"
            >
              Non {percentages.non || 0}%
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              style={{
                width: `${percentages.peut_etre || 0}%`,
                backgroundColor: "rgba(236, 163, 53, 0.85)",
                color: "#fff",
              }}
              aria-valuenow={percentages.peut_etre || 0}
              aria-valuemin="0"
              aria-valuemax="100"
            >
              Peut-être {percentages.peut_etre || 0}%
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              style={{
                width: `${percentages.mixte || 0}%`,
                backgroundColor: "rgb(170, 76, 187)",
                color: "#fff",
              }}
              aria-valuenow={percentages.mixte || 0}
              aria-valuemin="0"
              aria-valuemax="100"
            >
              Mixte {percentages.mixte || 0}%
            </div>
          </div>
          <div className="d-flex justify-content-around mt-3 text-center">
            <div>
              <span style={{ color: "rgba(76, 127, 175, 0.85)" }}>
                <strong>Oui:</strong>
              </span>
              {counts.oui || 0}
            </div>
            <div>
              <span style={{ color: "rgb(233, 94, 84)" }}>
                <strong>Non:</strong>
              </span>
              {counts.non || 0}
            </div>
            <div>
              <span style={{ color: "rgba(236, 163, 53, 0.85)" }}>
                <strong>Peut-être:</strong>
              </span>
              {counts.peut_etre || 0}
            </div>
            <div>
              <span style={{ color: "rgb(170, 76, 187)" }}>
                <strong>Mixte:</strong>
              </span>
              {counts.mixte || 0}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RagPage({ context }) {
  const { projectId, ragId } = useParams();
  const navigate = useNavigate();
  const [payload, setPayload] = useState(null);
  const [errors, setErrors] = useState([]);
  const [query, setQuery] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [ragDocuments, setRagDocuments] = useState([]);
  const [sortBy, setSortBy] = useState("-decision_date");
  const [status, setStatus] = useState(null);

  const current = payload?.current || null;
  const history = payload?.history || [];

  const sortedDocuments = useMemo(() => {
    const items = [...ragDocuments];
    if (sortBy === "decision_date") {
      items.sort((a, b) => (a.document.decision_date < b.document.decision_date ? -1 : 1));
    } else if (sortBy === "-decision_date") {
      items.sort((a, b) => (a.document.decision_date < b.document.decision_date ? 1 : -1));
    } else if (sortBy === "confidence_score") {
      items.sort((a, b) => (a.confidence_score < b.confidence_score ? 1 : -1));
    }
    return items;
  }, [ragDocuments, sortBy]);

  useEffect(() => {
    if (!projectId) {
      setErrors(["Invalid project route."]);
      return;
    }

    fetchRagContext(context.api, projectId, ragId)
      .then((data) => {
        setPayload(data);
        setErrors([]);
        setQuery(data.project?.natural_language_query || "");
      })
      .catch((error) => {
        setErrors(error.messages ?? [error.message]);
      });
  }, [context.api, projectId, ragId]);

  useEffect(() => {
    if (!ragId || !projectId) {
      return undefined;
    }

    let isActive = true;

    const pollStatus = async () => {
      try {
        const response = await fetchRagStatus(context.api, projectId, ragId);
        if (!isActive) {
          return;
        }
        setStatus(response.status);
        if (response.status === "completed") {
          const documents = await fetchRagDocuments(context.api, response.id);
          if (isActive) {
            setRagDocuments(documents);
            setPayload((prev) => {
              if (!prev) {
                return prev;
              }
              const updatedHistory = prev.history.map((entry) =>
                entry.id === response.id
                  ? {
                      ...entry,
                      status: response.status,
                      status_display: response.status_display,
                      valid_answer_count: response.valid_answer_count,
                      num_documents: response.num_documents,
                    }
                  : entry
              );
              return { ...prev, history: updatedHistory };
            });
          }
        }
      } catch (error) {
        if (isActive) {
          setErrors(error.messages ?? [error.message]);
        }
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 1200);

    return () => {
      isActive = false;
      window.clearInterval(intervalId);
    };
  }, [context.api, projectId, ragId]);

  const isProcessing = Boolean(ragId && status && status !== "completed");

  const handleAsk = async (event) => {
    event.preventDefault();
    if (!payload?.documents_ids?.length) {
      setErrors(["No selected documents found."]);
      return;
    }

    setIsSubmitting(true);
    setErrors([]);

    try {
      const response = await createRagEntry(context.api, projectId, {
        project_id: Number(projectId),
        query: query.trim().toLowerCase(),
        documents_ids: payload.documents_ids,
      });
      navigate(`/rag/${projectId}/${response.id}`);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (targetId) => {
    if (!window.confirm("Are you sure you want to remove this asked question?")) {
      return;
    }
    try {
      await deleteRagEntry(context.api, projectId, targetId);
      const updated = await fetchRagContext(context.api, projectId, ragId);
      setPayload(updated);
    } catch (error) {
      setErrors(error.messages ?? [error.message]);
    }
  };

  if (!payload) {
    return (
      <section className="container py-5 mt-5">
        <h1 className="text-center col-12 mb-5">Ask the documents</h1>
        {errors.map((message) => (
          <div className="alert alert-danger" key={message} role="alert">
            {message}
          </div>
        ))}
        {errors.length === 0 ? <p>Loading RAG workspace...</p> : null}
      </section>
    );
  }

  return (
    <section className="py-5 mt-5">
      <div className="container">
        <div className="mb-4">
          <a className="btn btn-primary mb-2" href={payload.urls.back}>
            <i className="bi bi-arrow-left" /> Back To Select New Documents
          </a>
          {ragId ? (
            <button
              className="btn btn-primary mb-2 ms-2"
              onClick={() => navigate(`/rag/${projectId}/`)}
              type="button"
            >
              <i className="fa-regular fa-search me-2" /> Ask new question
            </button>
          ) : null}
        </div>
      </div>

      {!ragId ? (
        <div className="container">
          <div className="col-sm-12 col-md-12 col-xl-11 mx-auto">
            <div className="container py-8">
              <h1 className="text-center col-12 mb-5">
                <i className="fa-regular fa-search me-3" /> Ask the documents
              </h1>
              <form className="row" onSubmit={handleAsk}>
                <div className="col-sm-12 col-lg-12 mb-3 text-center">
                  <div className="input-group mb-3">
                    <input
                      type="text"
                      name="query"
                      className="form-control"
                      placeholder="Ask what you want"
                      aria-label="question"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      required
                    />
                    <button
                      className="btn btn-outline-secondary"
                      type="submit"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? "Asking..." : "Ask"}
                    </button>
                  </div>
                </div>
              </form>
              <div className="text-center mb-2">
                <b>Number of selected documents: </b> {payload.number_documents}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="container">
          <div className="col-sm-12 col-md-12 col-xl-11 mx-auto">
            <div className="container py-8">
              <h1 className="text-center col-12 mb-5">Question: {current?.query}</h1>
            </div>
          </div>
        </div>
      )}

      {isProcessing ? (
        <div className="mt-5 d-flex justify-content-center">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Answering Question ...</span>
          </div>
          <span className="ms-3 fs-4 text-secondary">Answering Question ...</span>
        </div>
      ) : null}

      {ragId ? (
        <div className="container pb-5 px-4">
          <div className="fs-5 row" style={{ overflow: "auto" }}>
            <div className="col-12">
              <div>
                <h3>Considérations générales:</h3>
                <SummarySection current={current} />
                <RegleDroitSection current={current} />
                <KeyElementsTable current={current} />
                <LawArticlesTable current={current} />
                <ClosedStats current={current} />
                <h3 className="mb-5">Résultats obtenus à partir des documents</h3>
                <div className="col-4 d-flex align-items-center mb-3">
                  <label className="form-label me-2 mb-0" htmlFor="update_order_by">
                    <b className="text-nowrap">Sort by:</b>
                  </label>
                  <select
                    className="form-select"
                    id="update_order_by"
                    onChange={(event) => setSortBy(event.target.value)}
                    value={sortBy}
                  >
                    {current?.has_confidence_score ? (
                      <option value="confidence_score">Confidence Score</option>
                    ) : null}
                    <option value="decision_date">Decision Date (Ascending)</option>
                    <option value="-decision_date">Decision Date (Descending)</option>
                  </select>
                </div>
                <div className="row">
                  <hr />
                </div>
                <div id="ragAnswers">
                  {sortedDocuments.map((doc) => (
                    <RagAnswerCard documentRag={doc} key={doc.id} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="container pb-5 px-4" id="history-questions">
        <h3 className="text-center" style={{ paddingTop: "55px" }}>
          Asked Questions
        </h3>
        <table className="table table-hover">
          <thead>
            <tr>
              <th scope="col">Status</th>
              <th scope="col">Query</th>
              <th scope="col">Answers/Documents</th>
              <th scope="col">Created At</th>
              <th scope="col">Remove</th>
            </tr>
          </thead>
          <tbody>
            {history.length ? (
              history.map((entry) => (
                <RAGHistoryRow
                  entry={entry}
                  key={entry.id}
                  onDelete={handleDelete}
                  projectId={projectId}
                />
              ))
            ) : (
              <tr>
                <td colSpan={5} className="text-center text-muted">
                  No RAG entries found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default RagPage;
