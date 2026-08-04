import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { fetchDocumentContent } from "../../libs/document_content";

function DocumentMetadata({ document }) {
  return (
    <div className="container">
      <hr />
      <div className="px-3">
        <h3 className="text-end">
          <span className="badge text-bg-dark">{document.procedure_type}</span>
        </h3>
        <div className="ms-auto mt-3 text-start mb-3">
          <div>
            <b>{document.decision_type}</b>, du {document.decision_date || "-"}
            <b> Result: </b>
            {document.result || "-"}
          </div>
        </div>
        <div className="mb-3 ms-auto">
          <div>
            <b>Normes: </b>
            {document.standards || "-"}
          </div>
        </div>
      </div>
      <hr />
    </div>
  );
}

function DocumentContent({ content }) {
  if (content.html_text) {
    return (
      <div className="container p-3">
        <div dangerouslySetInnerHTML={{ __html: content.html_text }} />
      </div>
    );
  }

  if (content.raw_text) {
    return (
      <div className="container p-3">
        <pre
          className="m-3"
          style={{
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontFamily: "inherit",
          }}
        >
          {content.raw_text}
        </pre>
      </div>
    );
  }

  return <p className="text-center">No document content available.</p>;
}

function ContentDocument({ context }) {
  const { documentId } = useParams();
  const [payload, setPayload] = useState(null);
  const [errors, setErrors] = useState([]);

  useEffect(() => {
    if (!documentId) {
      setErrors(["Invalid document route."]);
      return;
    }

    fetchDocumentContent(context.api, documentId)
      .then((data) => {
        setPayload(data);
        setErrors([]);
      })
      .catch((error) => {
        setErrors(error.messages ?? [error.message]);
      });
  }, [context.api, documentId]);

  if (!payload) {
    return (
      <section className="container py-5 mt-5">
        <h2 className="pb-2 text-center">Document Content</h2>
        {errors.map((message) => (
          <div className="alert alert-danger" key={message} role="alert">
            {message}
          </div>
        ))}
        {errors.length === 0 ? <p>Loading document...</p> : null}
      </section>
    );
  }

  return (
    <section className="py-5 mt-5">
      <h2 className="pb-2 text-center">Document Content</h2>
      <DocumentMetadata document={payload.document} />
      <DocumentContent content={payload.content} />
      <div className="container-fluid px-4 py-5 my-5" />
    </section>
  );
}

export default ContentDocument;
