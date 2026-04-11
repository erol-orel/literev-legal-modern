import { useState } from "react";
import { Link, NavLink } from "react-router-dom";

import { staticAsset } from "../../libs/static";

function navClassName({ isActive }) {
  return `nav-link fs-5 ${isActive ? "active" : ""}`.trim();
}

function Navigation({ context }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { urls, user } = context;

  return (
    <header className="bg-dark fixed-top shadow-sm">
      <nav className="container navbar navbar-expand-lg navbar-dark bg-dark py-3">
        <div className="container-fluid px-0">
          <Link className="navbar-brand d-flex align-items-center" to={urls.home}>
            <img
              alt="LiteRev logo"
              className="img-fluid"
              src={staticAsset("images/logo_sans_fond.png")}
              style={{ maxHeight: "40px" }}
            />
            <span className="fs-4 ms-2">
              Lite<span className="text-primary">Rev</span>
            </span>
          </Link>
          <button
            aria-controls="react-shell-navigation"
            aria-expanded={isExpanded}
            aria-label="Toggle navigation"
            className="navbar-toggler"
            onClick={() => setIsExpanded((value) => !value)}
            type="button"
          >
            <span className="navbar-toggler-icon" />
          </button>
          <div
            className={`collapse navbar-collapse ${isExpanded ? "show" : ""}`}
            id="react-shell-navigation"
          >
            <ul className="navbar-nav ms-auto align-items-lg-center">
              <li className="nav-item">
                <NavLink className={navClassName} to={urls.product}>
                  Product
                </NavLink>
              </li>
              <li className="nav-item">
                <NavLink className={navClassName} to={urls.company}>
                  Company
                </NavLink>
              </li>
              <li className="nav-item">
                <NavLink className={navClassName} to={urls.blog}>
                  Blog
                </NavLink>
              </li>
              <li className="nav-item">
                <NavLink className={navClassName} to={urls.team}>
                  Team
                </NavLink>
              </li>
              <li className="nav-item">
                <a className="nav-link fs-5" href={urls.search}>
                  Search
                </a>
              </li>
              {user.isAuthenticated ? (
                <>
                  <li className="nav-item">
                    <span className="nav-link active fs-6 react-shell__user-email">
                      <i className="fa-regular fa-user me-2" />
                      {user.email}
                    </span>
                  </li>
                  <li className="nav-item">
                    <a className="nav-link fs-5" href={urls.logout}>
                      <i className="fa-solid fa-right-from-bracket me-2" />
                      Logout
                    </a>
                  </li>
                </>
              ) : (
                <li className="nav-item">
                  <a className="nav-link fs-5" href={urls.login}>
                    <i className="fa-solid fa-right-to-bracket me-2" />
                    Login
                  </a>
                </li>
              )}
            </ul>
          </div>
        </div>
      </nav>
    </header>
  );
}

export default Navigation;
