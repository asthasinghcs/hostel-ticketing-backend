import { defineConfig } from "@neon/config/v1";

// PostgreSQL is present on every Neon branch. Flask owns application auth.
// Preserve the selected production branch and its existing compute settings.
export default defineConfig({});
