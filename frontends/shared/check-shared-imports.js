const { readdir, readFile } = require("node:fs/promises");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const frontendsDir = path.join(repoRoot, "frontends");
const portals = ["admin-ui", "client-portal", "partner-portal"];

async function collectSourceFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectSourceFiles(fullPath));
      continue;
    }
    if (entry.isFile() && (fullPath.endsWith(".ts") || fullPath.endsWith(".tsx"))) {
      files.push(fullPath);
    }
  }

  return files;
}

function findInvalidImports(content) {
  const invalid = [];
  const importRegex = /from\s+["']([^"']+)["']/g;
  let match;

  while ((match = importRegex.exec(content)) !== null) {
    if (match[1].includes("../shared/")) {
      invalid.push(match[1]);
    }
  }

  return invalid;
}

async function main() {
  const violations = [];

  for (const portal of portals) {
    const srcDir = path.join(frontendsDir, portal, "src");
    const files = await collectSourceFiles(srcDir);
    for (const filePath of files) {
      const contents = await readFile(filePath, "utf8");
      const invalidImports = findInvalidImports(contents);
      if (invalidImports.length > 0) {
        violations.push({
          filePath,
          invalidImports,
          portal,
        });
      }
    }
  }

  if (violations.length > 0) {
    console.error("Invalid shared imports detected in portal sources:");
    for (const violation of violations) {
      const relativePath = path.relative(repoRoot, violation.filePath);
      console.error(
        `- ${violation.portal}/${relativePath}: ${violation.invalidImports.join(", ")}`
      );
    }
    process.exit(1);
  }

  console.log("Shared import check passed.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
