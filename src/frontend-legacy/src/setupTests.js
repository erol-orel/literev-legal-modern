import "@testing-library/jest-dom";

const reactDomTestUtilsActDeprecation =
  "Warning: `ReactDOMTestUtils.act` is deprecated in favor of `React.act`.";

const originalConsoleError = console.error;

beforeAll(() => {
  jest.spyOn(console, "error").mockImplementation((...args) => {
    if (
      typeof args[0] === "string" &&
      args[0].includes(reactDomTestUtilsActDeprecation)
    ) {
      return;
    }

    originalConsoleError(...args);
  });
});

afterAll(() => {
  console.error.mockRestore();
});
