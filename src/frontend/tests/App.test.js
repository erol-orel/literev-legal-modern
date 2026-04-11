import { render, screen } from "@testing-library/react";

import App from "../src/App";

const baseContext = {
  appName: "LiteRev Legal",
  urls: {
    home: "/",
    search: "/search/",
    team: "/team/",
    product: "/product/",
    company: "/company/",
    blog: "/blog/",
    login: "/accounts/login/",
    logout: "/accounts/logout/",
  },
  user: {
    email: "",
    isAuthenticated: false,
  },
};

function renderAppAt(pathname, context = baseContext) {
  window.history.pushState({}, "", pathname);
  return render(<App initialContext={context} />);
}

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
    renderAppAt("/", {
      ...baseContext,
      user: {
        email: "lawyer@example.com",
        isAuthenticated: true,
      },
    });

    expect(screen.getByText(/lawyer@example\.com/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /logout/i })).toHaveAttribute(
      "href",
      "/accounts/logout/"
    );
  });
});
