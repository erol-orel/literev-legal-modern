const fs = require("fs");
const path = require("path");

const isTestFile = (name) => /\.(test|spec)\.[jt]sx?$/.test(name);

function loadTests(dirPath) {
  for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
    const fullPath = path.join(dirPath, entry.name);

    if (entry.isDirectory()) {
      loadTests(fullPath);
      continue;
    }

    if (isTestFile(entry.name)) {
      require(fullPath);
    }
  }
}

// react-scripts only discovers test files under src/, so this file loads
// the real frontend test suite from ../tests/.
loadTests(path.resolve(__dirname, "../tests"));
