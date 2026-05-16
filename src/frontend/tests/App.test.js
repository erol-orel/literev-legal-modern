import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import App from "../src/App";

let mockInitialPath = "/";

jest.mock("react-router-dom", () => {
  const actual = jest.requireActual("react-router-dom");
  const React = require("react");
  return {
    ...actual,
    BrowserRouter: ({ children, ...props }) =>
      React.createElement(
        actual.MemoryRouter,
        { ...props, initialEntries: [mockInitialPath] },
        children
      ),
  };
});


const baseContext = {
  api: {
    historicalDeleteAll: "/api/project/historical/delete-all/",
    historicalProjects: "/api/project/historical/",
    projectApiBase: "/api/project/projects/",
    projectDeleteBase: "/api/project/projects/",
    documentContentBase: "/api/project/documents/",
    documentHighlightedBase: "/api/project/documents/rag/",
    tableSelectionBase: "/api/project/tableselect/",
    ragContextBase: "/api/project/rag/",
    ragDeleteBase: "/api/project/rag/",
    ragStatusBase: "/api/project-rags-by-project/",
    ragCreateBase: "/api/project-rags-by-project/",
    ragDocumentsBase: "/api/project-documents-rag/",
    runningProjects: "/api/project/running/",
    searchConvertQuery: "/api/project/search/convert-query/",
    searchPreview: "/api/project/search/preview/",
    searchProjects: "/api/project/search/projects/",
    searchValidate: "/api/project/search/validate/",
  },
  appName: "LiteRev Legal",
  appVersion: "0.13.0", // semantic-release
  search: {
    clusteringMinDocuments: 12,
    sources: [
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
    ],
  },
  urls: {
    blog: "/blog/",
    company: "/company/",
    historicalpage: "/historicalpage/",
    home: "/",
    projectBase: "/project/",
    ragBase: "/rag/",
    contentdocumentBase: "/contentdocument/",
    contentdocumentHighlightedBase: "/contentdocument_highlighted/",
    tableselectBase: "/tableselect/",
    login: "/accounts/login/",
    logout: "/accounts/logout/",
    product: "/product/",
    running: "/running/",
    search: "/search/",
    team: "/team/",
  },
  user: {
    email: "",
    isAuthenticated: false,
  },
};

const authenticatedContext = {
  ...baseContext,
  user: {
    email: "lawyer@example.com",
    isAuthenticated: true,
  },
};

function jsonResponse(payload) {
  return {
    json: async () => payload,
    ok: true,
  };
}

function renderAppAt(pathname, context = baseContext) {
  mockInitialPath = pathname;
  window.history.pushState({}, "", pathname);
  return render(<App initialContext={context} />);
}

afterEach(() => {
  jest.clearAllMocks();
  delete global.fetch;
});

describe("App", () => {
  it("renders the migrated home page from router state", () => {
    renderAppAt("/");

    expect(
      screen.getByRole("heading", {
        name: /smarter research\. better insights\./i,
      })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /get started/i })).toHaveAttribute(
      "href",
      "/search/"
    );
  });

  it("redirects unauthenticated users from React-owned authenticated routes", async () => {
  const originalLocation = window.location;
  const assignSpy = jest.fn();
  Object.defineProperty(window, "location", {
    writable: true,
    value: { ...window.location, assign: assignSpy },
  });

  try {
    renderAppAt("/running/");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /redirecting to login/i
    );
    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith(
        "/accounts/login/?next=%2Frunning%2F"
      );
    });
  } finally {
    Object.defineProperty(window, "location", {
      writable: true,
      value: originalLocation,
    });
  }
  });


  it("renders the migrated search page from router state", () => {
    renderAppAt("/search/", authenticatedContext);

    expect(
      screen.getByRole("heading", { name: /project search/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/literev version 0\.12\.0/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
    expect(
      screen.getByText(/minimum number of documents for clustering/i)
    ).toHaveTextContent("12");
  });

  it("evaluates searches from the React search page", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse({
        can_cluster: true,
        can_continue: true,
        clustering_min_documents: 12,
        natural_language_query: "",
        project_name: "Housing rights",
        query: '"contrat" AND "résiliation"',
        range_begin_date: "2020-01-01",
        range_end_date: "2020-12-31",
        selected_indices: ["chambre_administrative"],
        total_documents: 42,
      })
    );

    renderAppAt("/search/", authenticatedContext);

    fireEvent.change(screen.getByLabelText(/project name/i), {
      target: { value: "Housing rights" },
    });
    fireEvent.change(screen.getByLabelText(/boolean query/i), {
      target: { value: '"contrat" AND "résiliation"' },
    });
    fireEvent.change(screen.getByLabelText(/decision date from/i), {
      target: { value: "2020-01-01" },
    });
    fireEvent.change(screen.getByLabelText(/decision date to/i), {
      target: { value: "2020-12-31" },
    });
    fireEvent.click(screen.getByRole("button", { name: /evaluate/i }));

    expect(await screen.findByText(/42 documents\./i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/project/search/preview/",
      expect.objectContaining({
        method: "POST",
      })
    );
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual(
      expect.objectContaining({
        project_name: "Housing rights",
        query: '"contrat" AND "résiliation"',
        selected_indices: ["chambre_administrative"],
      })
    );
  });

  it("renders the running projects page from router state", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse({
        projects: [
          {
            best_dbcv: 0,
            can_delete: true,
            can_open_project: true,
            can_restart: true,
            creation_date: "2026-04-12",
            id: 5,
            is_finish: false,
            is_shared: false,
            name: "Running Alpha",
            processed_documents: 2,
            progress: {
              kind: "progress",
              label: "2/10",
              message: "Collecting documents",
              percentage: 20,
            },
            project_url: "/project/5/",
            query: '"alpha"',
            range_begin_date: "2020-01-01",
            range_end_date: "2020-12-31",
            selected_indices: ["chambre_administrative"],
            step: "getting_documents",
            step_label: "Getting_Documents",
            total_documents: 10,
          },
        ],
      })
    );

    renderAppAt("/running/", authenticatedContext);

    expect(
      await screen.findByRole("heading", { name: /project status/i })
    ).toBeInTheDocument();
    expect(await screen.findByText(/running alpha/i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/project/running/",
      expect.objectContaining({ credentials: "same-origin" })
    );
  });

  it("filters historical projects from the React page", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          projects: [],
          query_filter: "",
          sort_type: "more_documents_first",
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          projects: [
            {
              best_dbcv: 0.321,
              can_delete: true,
              can_open_project: true,
              can_restart: false,
              creation_date: "2026-04-12",
              id: 9,
              is_finish: true,
              is_shared: false,
              name: "Historical Water",
              processed_documents: 3,
              progress: { kind: "status", label: "Completed", message: "Completed" },
              project_url: "/project/9/",
              query: "water rights",
              range_begin_date: "2020-01-01",
              range_end_date: "2020-12-31",
              selected_indices: ["chambre_administrative"],
              step: "plotting",
              step_label: "Plotting",
              total_documents: 3,
            },
          ],
          query_filter: "water",
          sort_type: "less_documents_first",
        })
      );

    renderAppAt("/historicalpage/", authenticatedContext);

    expect(
      await screen.findByRole("heading", { name: /historical search/i })
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^search$/i), {
      target: { value: "water" },
    });
    fireEvent.change(screen.getByLabelText(/sorting type/i), {
      target: { value: "less_documents_first" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));

    expect(await screen.findByText(/historical water/i)).toBeInTheDocument();
    expect(await screen.findByText(/filter by keywords: water/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenLastCalledWith(
        "/api/project/historical/?search=water&sort_type=less_documents_first",
        expect.objectContaining({ credentials: "same-origin" })
      );
    });
  });


  it("renders the project overview page from router state", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse({
        cluster_summaries: [
          {
            cluster_id: 3,
            cluster_order: 1,
            representative_document: {
              decision_type: "Decision",
              document_id: "DOC-001",
              procedure_type: "Appeal",
              result: "ADMIS",
            },
            summary_text: "",
            topic: "housing, rights, tenancy",
            topic_color: "#ff00ff",
            topic_label: "housing, rights, tenancy",
            total_documents: 5,
          },
        ],
        filters: {
          refinement_count: 1,
          refinement_limit: 15,
          types: [
            {
              input_kind: "text",
              label: "Keyword Search",
              options: [],
              placeholder: "Criteria",
              value: "Keyword",
            },
          ],
        },
        no_clusters: false,
        plot: null,
        project: {
          best_dbcv: 0.42,
          can_ask_top_docs: true,
          can_delete: true,
          creation_date: "2026-04-12",
          id: 5,
          is_finish: true,
          is_running: false,
          is_shared: false,
          name: "Overview Project",
          natural_language_query: "",
          processed_documents: 5,
          progress: { kind: "status", label: "Plotting", message: "Plotting" },
          query: '"housing"',
          range_begin_date: "2020-01-01",
          range_end_date: "2020-12-31",
          selected_indices: ["chambre_administrative"],
          step: "plotting",
          step_label: "Plotting",
          total_documents: 5,
        },
        refinements: [
          {
            can_delete: true,
            filters: {},
            id: 9,
            name: "Initial refinement",
            open_url: "/tableselect/5/9/",
            owner_name: "lawyer@example.com",
          },
        ],
      })
    );

    renderAppAt("/project/5/", authenticatedContext);

    expect(
      await screen.findByRole("heading", { name: /project: overview project/i })
    ).toBeInTheDocument();
    expect(await screen.findByText(/cluster summary table/i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/project/projects/5/overview/",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("previews refinements from the project overview page", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          cluster_summaries: [],
          filters: {
            refinement_count: 0,
            refinement_limit: 15,
            types: [
              {
                input_kind: "text",
                label: "Keyword Search",
                options: [],
                placeholder: "Criteria",
                value: "Keyword",
              },
            ],
          },
          no_clusters: true,
          plot: null,
          project: {
            best_dbcv: 0.42,
            can_ask_top_docs: true,
            can_delete: true,
            creation_date: "2026-04-12",
            id: 5,
            is_finish: true,
            is_running: false,
            is_shared: false,
            name: "Overview Project",
            natural_language_query: "",
            processed_documents: 5,
            progress: { kind: "status", label: "Plotting", message: "Plotting" },
            query: '"housing"',
            range_begin_date: "2020-01-01",
            range_end_date: "2020-12-31",
            selected_indices: ["chambre_administrative"],
            step: "plotting",
            step_label: "Plotting",
            total_documents: 5,
          },
          refinements: [],
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          can_continue: true,
          filters: {},
          number_documents: 5,
        })
      );

    renderAppAt("/project/5/", authenticatedContext);

    await screen.findByRole("heading", { name: /project: overview project/i });
    fireEvent.click(screen.getByRole("button", { name: /see all documents/i }));

    expect(
      await screen.findByText(/the refinement contains 5 documents\./i)
    ).toBeInTheDocument();
    expect(global.fetch).toHaveBeenLastCalledWith(
      "/api/project/projects/5/filters/preview/",
      expect.objectContaining({ method: "POST" })
    );
  });


  it("renders the table-selection page from router state", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse({
        canonical_url: `/tableselect/5/9/11/page=1/order_by=decision_date/`,
        counts: {
          chosen: 1,
          initial: 2,
          neighbour: 0,
          total_display: 2,
        },
        current_iteration_id: 11,
        filters: {
          excluded_set_html: "",
          union_sets_html: "(Keyword: housing)",
        },
        iterations: [
          {
            id: 11,
            is_active: true,
            is_parent: false,
            is_root: true,
            name: "Iteration 1: (2 documents)",
            owner_id: 1,
          },
        ],
        processing_filters: false,
        project: {
          can_iterate: true,
          creation_date: "2026-04-12",
          id: 5,
          name: "Overview Project",
          processed_documents: 2,
          query: '"housing"',
          range_begin_date: "2020-01-01",
          range_end_date: "2020-12-31",
          step: "plotting",
          step_number: 0,
        },
        refinement: {
          id: 9,
          iterations_limit: 10,
          name: "Housing refinement",
        },
        table: {
          current_page: 1,
          has_es_scores: false,
          has_hdbscan_scores: false,
          rows: [
            {
              content_url: "/contentdocument/1",
              decision_date: "2020-01-01",
              decision_type: "Decision 1",
              document_pk: 1,
              id: 101,
              is_check: true,
              is_initial: true,
              procedure_type: "Appeal",
              result: "ADMIS",
              sample_document: "Housing contract excerpt",
              standards: "CEDH.6",
            },
          ],
          sort_by: "decision_date",
          sort_options: [
            { label: "Decision Date (Ascending)", value: "decision_date" },
          ],
          total_pages: 1,
        },
        urls: {
          back_to_filter: "/project/5/",
          default: "/tableselect/5/9/",
          project_rag: "/rag/5/",
        },
        warnings: [],
      })
    );

    renderAppAt(
      "/tableselect/5/9/11/page=1/order_by=decision_date/",
      authenticatedContext
    );

    expect(
      await screen.findByRole("heading", { name: /results table/i })
    ).toBeInTheDocument();
    expect(await screen.findByText(/keyword: housing/i)).toBeInTheDocument();
    expect(await screen.findByText(/housing contract excerpt/i)).toBeInTheDocument();
  });

  it("updates bulk selection from the table-selection page", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          canonical_url: `/tableselect/5/9/11/page=1/order_by=decision_date/`,
          counts: { chosen: 1, initial: 2, neighbour: 0, total_display: 2 },
          current_iteration_id: 11,
          filters: { excluded_set_html: "", union_sets_html: "" },
          iterations: [],
          processing_filters: false,
          project: {
            can_iterate: true,
            creation_date: "2026-04-12",
            id: 5,
            name: "Overview Project",
            processed_documents: 2,
            query: '"housing"',
            range_begin_date: "2020-01-01",
            range_end_date: "2020-12-31",
            step: "plotting",
            step_number: 0,
          },
          refinement: { id: 9, iterations_limit: 10, name: "Housing refinement" },
          table: {
            current_page: 1,
            has_es_scores: false,
            has_hdbscan_scores: false,
            rows: [
              {
                content_url: "/contentdocument/1",
                decision_date: "2020-01-01",
                decision_type: "Decision 1",
                document_pk: 1,
                id: 101,
                is_check: true,
                is_initial: true,
                procedure_type: "Appeal",
                result: "ADMIS",
                sample_document: "Housing contract excerpt",
                standards: "CEDH.6",
              },
            ],
            sort_by: "decision_date",
            sort_options: [
              { label: "Decision Date (Ascending)", value: "decision_date" },
            ],
            total_pages: 1,
          },
          urls: {
            back_to_filter: "/project/5/",
            default: "/tableselect/5/9/",
            project_rag: "/rag/5/",
          },
          warnings: [],
        })
      )
      .mockResolvedValueOnce(jsonResponse({ detail: "Selection updated." }))
      .mockResolvedValueOnce(
        jsonResponse({
          canonical_url: `/tableselect/5/9/11/page=1/order_by=decision_date/`,
          counts: { chosen: 2, initial: 2, neighbour: 0, total_display: 2 },
          current_iteration_id: 11,
          filters: { excluded_set_html: "", union_sets_html: "" },
          iterations: [],
          processing_filters: false,
          project: {
            can_iterate: true,
            creation_date: "2026-04-12",
            id: 5,
            name: "Overview Project",
            processed_documents: 2,
            query: '"housing"',
            range_begin_date: "2020-01-01",
            range_end_date: "2020-12-31",
            step: "plotting",
            step_number: 0,
          },
          refinement: { id: 9, iterations_limit: 10, name: "Housing refinement" },
          table: {
            current_page: 1,
            has_es_scores: false,
            has_hdbscan_scores: false,
            rows: [
              {
                content_url: "/contentdocument/1",
                decision_date: "2020-01-01",
                decision_type: "Decision 1",
                document_pk: 1,
                id: 101,
                is_check: null,
                is_initial: true,
                procedure_type: "Appeal",
                result: "ADMIS",
                sample_document: "Housing contract excerpt",
                standards: "CEDH.6",
              },
            ],
            sort_by: "decision_date",
            sort_options: [
              { label: "Decision Date (Ascending)", value: "decision_date" },
            ],
            total_pages: 1,
          },
          urls: {
            back_to_filter: "/project/5/",
            default: "/tableselect/5/9/",
            project_rag: "/rag/5/",
          },
          warnings: [],
        })
      );

    renderAppAt(
      "/tableselect/5/9/11/page=1/order_by=decision_date/",
      authenticatedContext
    );

    await screen.findByRole("button", { name: /check all to maybe/i });
    fireEvent.click(screen.getByRole("button", { name: /check all to maybe/i }));

    expect(await screen.findByText(/selection updated\./i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      "/api/project/tableselect/5/9/check-all/",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("renders the document content page from router state", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse({
        document: {
          id: 12,
          procedure_type: "Appeal",
          decision_type: "Decision",
          decision_date: "2020-01-01",
          result: "ADMIS",
          standards: "CEDH.6",
        },
        content: {
          html_text: "<p>HTML document body</p>",
          raw_text: "Raw document body",
        },
      })
    );

    renderAppAt("/contentdocument/12", authenticatedContext);

    expect(await screen.findByRole("heading", { name: /document content/i })).toBeInTheDocument();
    expect(await screen.findByText(/appeal/i)).toBeInTheDocument();
    expect(screen.getByText(/html document body/i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/project/documents/12/",
      expect.any(Object)
    );
  });

  it("renders the highlighted document content page from router state", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse({
        document: {
          id: 5,
          procedure_type: "Appeal",
          decision_type: "Decision",
          decision_date: "2020-01-01",
          result: "ADMIS",
          standards: "CEDH.6",
        },
        content: {
          html_text: "",
          raw_text: "Raw document body",
          highlighted_text: '<span style="background-color: #FFFF77">Highlight</span>',
        },
      })
    );

    renderAppAt("/contentdocument_highlighted/5/", authenticatedContext);

    expect(await screen.findByRole("heading", { name: /document content/i })).toBeInTheDocument();
    expect(await screen.findByText(/highlight/i)).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/project/documents/rag/5/highlighted/",
      expect.any(Object)
    );
  });

  it("renders the rag page from router state", async () => {
    global.fetch = jest.fn().mockResolvedValueOnce(
      jsonResponse({
        project: { id: 3, name: "RAG Project", natural_language_query: "" },
        current: null,
        history: [],
        documents_ids: [10, 11],
        number_documents: 2,
        refinement: { id: 7, iteration_id: 2 },
        urls: { back: "/project/3/", rag_base: "/rag/3/" },
      })
    );

    renderAppAt("/rag/3", authenticatedContext);

    expect(
      await screen.findByRole("heading", { name: /ask the documents/i })
    ).toBeInTheDocument();
    const label = await screen.findByText(/number of selected documents/i);
    expect(label.parentElement).toHaveTextContent("2");
  });

  it("renders the rag results page from router state", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          project: { id: 3, name: "RAG Project", natural_language_query: "" },
          current: {
            id: 5,
            query: "Question",
            status: "completed",
            status_display: "Completed",
            summary_text: "Summary",
            considerations: [],
            regle_droit: "",
            key_elements: [],
            law_articles: [],
            show_closed_stats: false,
            counts: { oui: 0, non: 0, peut_etre: 0, mixte: 0 },
            percentages: { oui: 0, non: 0, peut_etre: 0, mixte: 0 },
            has_section_ans: false,
            has_confidence_score: false,
            valid_answer_count: 1,
            num_documents: 1,
          },
          history: [],
          documents_ids: [10],
          number_documents: 1,
          refinement: { id: 7, iteration_id: 2 },
          urls: { back: "/project/3/", rag_base: "/rag/3/" },
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: 5,
          project: 3,
          query: "Question",
          status: "completed",
          status_display: "Completed",
          valid_answer_count: 1,
          num_documents: 1,
        })
      )
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 99,
            answer: "Answer",
            citation: "Citation",
            confidence_score: null,
            document: {
              url_document: "/contentdocument_highlighted/99/",
              procedure_type: "Appeal",
              decision_type: "Decision",
              decision_date: "2020-01-01",
              result: "ADMIS",
              standards: "",
            },
          },
        ])
      );

    renderAppAt("/rag/3/5", authenticatedContext);

    expect(await screen.findByText(/question:/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/answer:/i, { selector: "b" })
    ).toBeInTheDocument();
  });

  it("renders the migrated team page from router state", () => {
    renderAppAt("/team/");

    expect(
      screen.getByRole("heading", {
        name: /meet the team behind literev legal\./i,
      })
    ).toBeInTheDocument();
    expect(screen.getByText(/aziza merzouki/i)).toBeInTheDocument();
  });

  it("renders placeholder pages for routes without migrated content", () => {
    renderAppAt("/product/");

    expect(screen.getByRole("heading", { name: /product/i })).toBeInTheDocument();
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
  });

  it("renders authenticated navigation state", () => {
    renderAppAt("/", authenticatedContext);

    expect(screen.getByText(/lawyer@example\.com/i)).toBeInTheDocument();
    // expect(screen.getByRole("link", { name: /running/i })).toHaveAttribute(
    //   "href",
    //   "/running/"
    // );
    // expect(screen.getByRole("link", { name: /history/i })).toHaveAttribute(
    //   "href",
    //   "/historicalpage/"
    // );
    expect(screen.getByRole("link", { name: /logout/i })).toHaveAttribute(
      "href",
      "/accounts/logout/"
    );
  });
});
