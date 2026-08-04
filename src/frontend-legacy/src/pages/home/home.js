import PartnersSection from "../../components/public/partners_section";
import { staticAsset } from "../../libs/static";

function Home({ urls }) {
  return (
    <>
      <div className="d-flex justify-content-center align-items-center color-b react-shell__hero">
        <div className="container-md text-center">
          <span className="text-light logo-literev mb-4 d-block">
            Lite<span className="text-primary">Rev</span>
          </span>
          <a
            className="fs-3 btn btn-primary btn-lg px-4 me-md-2 mt-4 mb-5"
            href={urls.search}
          >
            Get Started
          </a>
          <div className="text-center text-light fs-2 fs-sm-3 fs-md-1 mt-5">
            <h1 className="mb-4 d-block display-4 lh-1">
              Smarter research. Better insights.
            </h1>
          </div>
        </div>
      </div>

      <div style={{ backgroundColor: "#f8f9fa" }}>
        <div className="container col-xxl-8 px-4 py-5">
          <div className="container-fluid py-5 text-center">
            <h2 className="display-5 fw-bold text-center">About</h2>
            <p className="col-md-10 text-start fs-4 mx-auto react-shell__lead">
              LiteRev Legal reduces legal research time by surfacing relationships
              between topics, decisions, and document clusters. The platform helps
              legal researchers move from Boolean search to clustering, refinement,
              and citation-backed question answering.
            </p>
            <a className="text-center btn btn-primary btn-lg" href={urls.company}>
              Learn more
            </a>
          </div>
        </div>
      </div>

      <div style={{ backgroundColor: "#e6f1f0" }}>
        <div className="container col-xxl-8 px-4 py-5">
          <div className="container-fluid py-5">
            <h2 className="display-5 fw-bold text-center">How it works</h2>
            <div className="col-md-12 justify-content-center">
              <img
                alt="LiteRev Legal workflow overview"
                className="img-fluid"
                src={staticAsset("images/about-image.png")}
              />
            </div>
          </div>
        </div>
      </div>

      <PartnersSection />
    </>
  );
}

export default Home;
