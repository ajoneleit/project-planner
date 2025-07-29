// next.config.ts or next.config.js
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Remove: output: "standalone",
  images: { unoptimized: true }, // fine to keep
};

export default nextConfig;
