/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_ONBOARDING_ENABLED?: string;
  readonly NEFT_DEMO_ADMIN_EMAIL?: string;
  readonly NEFT_DEMO_ADMIN_PASSWORD?: string;
  readonly BASE_URL?: string;

  // Legacy variables kept for backward compatibility
  readonly VITE_CORE_API_BASE?: string;
  readonly VITE_AUTH_API_BASE?: string;
  readonly VITE_AI_API_BASE?: string;
  readonly VITE_ADMIN_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
