import preact from "@preact/preset-vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [preact()],
  server: { proxy: { "/api": "http://localhost:8080" } },
  test: { environment: "node" },
});
