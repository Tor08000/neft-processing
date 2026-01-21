/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_LOCALE?: string;
  readonly VITE_ONBOARDING_ENABLED?: string;
  readonly BASE_URL?: string;

  // Backward compatibility for legacy configuration variables
  readonly VITE_CORE_API_BASE?: string;
  readonly VITE_AUTH_API_BASE?: string;
  readonly VITE_AI_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
