const fs = require("node:fs");
const path = require("node:path");

/**
 * app.json plus Firebase when its config file is present. google-services.json is not kept in
 * git; a build that has it can receive instant push alerts, and one without it still gets alerts
 * from background checks.
 */
module.exports = ({ config }) => {
  if (!fs.existsSync(path.join(__dirname, "google-services.json"))) return config;
  return { ...config, android: { ...config.android, googleServicesFile: "./google-services.json" } };
};
