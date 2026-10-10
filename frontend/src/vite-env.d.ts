/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin for split deploys, e.g. https://agentops.onrender.com.
   *  Leave unset for the all-in-one (same-origin) Docker/Render deployment. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
