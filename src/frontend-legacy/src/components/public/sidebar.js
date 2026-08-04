import { NavLink } from "react-router-dom";

const SIDEBAR_ITEMS = [
  { label: "New Project", icon: "fa-solid fa-magnifying-glass", to: "search" },
  { label: "Running",     icon: "fa-solid fa-gears",            to: "running" },
  { label: "History",     icon: "fa-solid fa-database",         to: "historicalpage" },
];

function sidebarLinkClass({ isActive }) {
  return `nav-link d-flex align-items-center ${
    isActive ? "active bg-primary text-dark rounded-pill" : "text-white"
  }`;
}

function Sidebar({ context }) {
  if (!context.user.isAuthenticated) {
    return null;
  }

  const { appVersion, urls } = context;

  return (
    <aside className="react-shell__sidebar bg-dark text-white p-3 d-flex flex-column">
      <ul className="nav nav-pills flex-column fs-5 mb-auto">
        {SIDEBAR_ITEMS.map((item) => (
          <li className="nav-item mb-2" key={item.to}>
            <NavLink className={sidebarLinkClass} to={urls[item.to]}>
              <i className={`${item.icon} me-3`} />
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      {appVersion ? (
        <div
          className="react-shell__sidebar-version border-top pt-3 mt-3 small text-white-50"
        >
          LiteRev Version {appVersion}
        </div>
      ) : null}
    </aside>
  );
}

export default Sidebar;
