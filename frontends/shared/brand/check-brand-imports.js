import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const brandDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)));

async function collectCssFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectCssFiles(fullPath));
      continue;
    }
    if (entry.isFile() && entry.name.endsWith(".css")) {
      files.push(fullPath);
    }
  }

  return files;
}

function findInvalidImports(content) {
  const invalid = [];
  const importRegex = /@import\s+["']([^"']+)["']/g;
  let match;

  while ((match = importRegex.exec(content)) !== null) {
    if (match[1].includes("../")) {
      invalid.push(match[1]);
    }
  }

  return invalid;
}

const cssFiles = await collectCssFiles(brandDir);
const violations = [];

for (const filePath of cssFiles) {
  const contents = await readFile(filePath, "utf8");
  const invalidImports = findInvalidImports(contents);
  if (invalidImports.length > 0) {
    violations.push({ filePath, invalidImports });
  }
}

if (violations.length > 0) {
  console.error("Invalid @import paths detected inside shared/brand:");
  for (const violation of violations) {
    const relativePath = path.relative(brandDir, violation.filePath);
    console.error(`- ${relativePath}: ${violation.invalidImports.join(", ")}`);
  }
  process.exit(1);
}

console.log("Brand import check passed.");
