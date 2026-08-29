const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle so the Docker runtime image stays small.
  output: "standalone",
  reactStrictMode: true,
  // This app is the workspace root (avoids Next picking up a stray parent lockfile).
  turbopack: {
    root: __dirname,
  },
  outputFileTracingRoot: path.join(__dirname),
};

module.exports = nextConfig;
