import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The browser tests build into their own folder, against a fake API.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  agentRules: false,
  allowedDevOrigins: ["127.0.0.1"],
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
