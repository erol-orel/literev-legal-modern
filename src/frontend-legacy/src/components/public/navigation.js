import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import {
  AUTHENTICATED_NAVIGATION_ITEMS,
  PUBLIC_NAVIGATION_ITEMS,
} from "../../libs/routes";
import { staticAsset } from "../../libs/static";

function navClassName({ isActive }) {
  return `nav-link fs-5 ${isActive ? "active" : ""}`.trim();
}

function NavigationLink({ item, onNavigate, urls }) {
  return (
    <li className="nav-item">
      <NavLink className={navClassName} onClick={onNavigate} to={urls[item.to]}>
        {item.label}
      </NavLink>
    </li>
  );
}

function Navigation({ context }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const location = useLocation();
  const { urls, user } = context;

  const navigationItems = useMemo(() => {
    if (user.isAuthenticated) {
      return [...PUBLIC_NAVIGATION_ITEMS, ...AUTHENTICATED_NAVIGATION_ITEMS];
    }

    return PUBLIC_NAVIGATION_ITEMS;
  }, [user.isAuthenticated]);

  useEffect(() => {
    setIsExpanded(false);
  }, [location.pathname]);

  return (
    <header className="bg-dark fixed-top shadow-sm">
      <nav className="react-shell__navbar navbar navbar-expand-lg navbar-dark bg-dark py-3">
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
              {navigationItems.map((item) => (
                <NavigationLink
                  item={item}
                  key={item.to}
                  onNavigate={() => setIsExpanded(false)}
                  urls={urls}
                />
              ))}
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
