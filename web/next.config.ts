import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true
  },
  // Disable server-based features for static export
  // Ensure static files work with FastAPI serving
  basePath: "",
  assetPrefix: "",
};

export default nextConfig;
