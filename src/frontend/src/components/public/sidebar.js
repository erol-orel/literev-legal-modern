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

  const { urls } = context;

  return (
    <aside className="react-shell__sidebar bg-dark text-white p-3">
      <ul className="nav nav-pills flex-column fs-5">
        {SIDEBAR_ITEMS.map((item) => (
          <li className="nav-item mb-2" key={item.to}>
            <NavLink className={sidebarLinkClass} to={urls[item.to]}>
              <i className={`${item.icon} me-3`} />
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export default Sidebar;
