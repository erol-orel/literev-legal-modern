import { render, screen } from "@testing-library/react";

import App from "../src/App";

describe("App", () => {
  it("renders the frontend heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /literev legal frontend/i })
    ).toBeInTheDocument();
  });

  it("renders the migration note", () => {
    render(<App />);

    expect(
      screen.getByText(/backend migration remains in django for now/i)
    ).toBeInTheDocument();
  });
});
