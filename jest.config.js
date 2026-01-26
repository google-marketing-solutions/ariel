module.exports = {
  // Automatically clear mock calls and instances between every test
  clearMocks: true,

  // The directory where Jest should output its coverage files
  coverageDirectory: "coverage",

  // An array of regexp pattern strings used to skip coverage collection
  coveragePathIgnorePatterns: [
    "/node_modules/"
  ],

  // A list of reporter names that Jest uses when writing coverage reports
  coverageReporters: [
    "json",
    "text",
    "lcov",
    "clover"
  ],

  // A list of paths to modules that run some code to configure or set up the testing framework before each test
  setupFilesAfterEnv: [],

  // The test environment that will be used for testing
  testEnvironment: "jsdom",

  // The glob patterns Jest uses to detect test files
  testMatch: [
    "**/__tests__/**/*.js?(x)",
    "**/?(*.)+(spec|test).js?(x)"
  ],

  // An array of regexp pattern strings that are matched against all test paths, matched tests are skipped
  testPathIgnorePatterns: [
    "/node_modules/"
  ],

  // This option allows use of a custom resolver
  resolver: null,

  // Automatically reset mock state between every test
  resetMocks: false,

  // The path to a module that runs some code to configure or set up the testing environment before each test
  setupFiles: [],

  // A list of paths to directories that Jest should use to search for files in
  roots: [
    "<rootDir>/static/js"
  ],

  // The paths to modules that run some code to configure or set up the testing environment after each test
  // setupFilesAfterEnv: ["<rootDir>/setupTests.js"],

  // A map from regular expressions to paths to transformers
  transform: {
    "^.+\.js$": "babel-jest"
  },
};
