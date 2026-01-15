/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_LOCALE?: string;
  readonly VITE_PWA_MODE?: string;
  readonly VITE_PUSH_PUBLIC_KEY?: string;
  readonly VITE_MARKETPLACE_ORDERING?: string;
  readonly VITE_SELF_SIGNUP_ENABLED?: string;
  readonly VITE_ONBOARDING_DOCS_REQUIRED?: string;
  readonly VITE_CONTRACT_SIMPLE_SIGN_ENABLED?: string;
  readonly VITE_AUTO_ACTIVATE_AFTER_SIGN?: string;
  readonly VITE_INDIVIDUAL_SIGNUP_ENABLED?: string;
  readonly BASE_URL?: string;

  // Backward compatibility for legacy configuration variables
  readonly VITE_CORE_API_BASE?: string;
  readonly VITE_AUTH_API_BASE?: string;
  readonly VITE_AI_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
