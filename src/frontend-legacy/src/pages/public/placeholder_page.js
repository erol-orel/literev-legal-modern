function PlaceholderPage({ description, heading, urls }) {
  return (
    <section className="container react-shell__placeholder-page py-5">
      <div className="row justify-content-center">
        <div className="col-lg-8">
          <div className="card shadow-sm border-0 react-shell__placeholder-card mt-5">
            <div className="card-body p-5 text-center">
              <span className="badge bg-light text-primary border mb-3">
                Coming soon
              </span>
              <h1 className="display-5 fw-bold">{heading}</h1>
              <p className="fs-4 text-muted mb-4">{description}</p>
              <div className="d-flex gap-3 justify-content-center flex-wrap">
                <a className="btn btn-primary btn-lg" href={urls.home}>
                  Back to home
                </a>
                <a className="btn btn-outline-primary btn-lg" href={urls.search}>
                  Open search
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default PlaceholderPage;
