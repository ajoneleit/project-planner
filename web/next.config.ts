import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Removed static export for now - will serve via FastAPI
  // output: "export",
  // trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // Removed rewrites - using direct backend calls instead
};

export default nextConfig;
