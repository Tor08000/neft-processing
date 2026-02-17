import js from "@eslint/js";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import reactRefreshPlugin from "eslint-plugin-react-refresh";
import globals from "globals";

const typescriptEslintPlugin = {
  rules: {
    "consistent-type-assertions": {
      meta: {
        type: "problem",
        schema: [{ type: "object", additionalProperties: true }],
        messages: {
          noTypeAssertions: "Type assertions are forbidden. Use proper typing or normalization instead.",
        },
      },
      create(context) {
        return {
          TSAsExpression(node) {
            context.report({ node, messageId: "noTypeAssertions" });
          },
          TSTypeAssertion(node) {
            context.report({ node, messageId: "noTypeAssertions" });
          },
        };
      },
    },
  },
};

export default [
  { ignores: ["dist", "public/sw.js"] },
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "@typescript-eslint": typescriptEslintPlugin,
      "react-hooks": reactHooksPlugin,
      "react-refresh": reactRefreshPlugin,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooksPlugin.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/consistent-type-assertions": ["error", { assertionStyle: "never" }],
    },
  },
];
