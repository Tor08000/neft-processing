// Minimal Vitest type stubs to satisfy TypeScript during builds.
declare module "vitest" {
  export const describe: (...args: any[]) => any;
  export const it: (...args: any[]) => any;
  export const test: (...args: any[]) => any;
  export const expect: any;
  export const beforeAll: (...args: any[]) => any;
  export const beforeEach: (...args: any[]) => any;
  export const afterAll: (...args: any[]) => any;
  export const afterEach: (...args: any[]) => any;
  export const vi: any;
}

declare global {
  const describe: (...args: any[]) => any;
  const it: (...args: any[]) => any;
  const test: (...args: any[]) => any;
  const expect: any;
  const beforeAll: (...args: any[]) => any;
  const beforeEach: (...args: any[]) => any;
  const afterAll: (...args: any[]) => any;
  const afterEach: (...args: any[]) => any;
  const vi: any;
}

export {};
