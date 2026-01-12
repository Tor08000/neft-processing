const { readdir, readFile, access } = require("node:fs/promises");
const path = require("node:path");

const portalRoot = process.cwd();
const portalSrcDir = path.resolve(portalRoot, "src");

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

function resolvesToSharedOutsidePortal(importPath, filePath) {
  if (!importPath.startsWith(".")) {
    return false;
  }

  const resolvedPath = path.resolve(path.dirname(filePath), importPath);
  const pathSegments = resolvedPath.split(path.sep);

  return pathSegments.includes("shared") && !resolvedPath.startsWith(portalSrcDir);
}

async function main() {
  try {
    await access(portalSrcDir);
  } catch (error) {
    console.error(`Cannot find src dir at ${portalSrcDir}`);
    process.exit(1);
  }

  const files = await collectSourceFiles(portalSrcDir);
  const violations = [];

  for (const filePath of files) {
    const contents = await readFile(filePath, "utf8");
    const lines = contents.split(/\r?\n/);

    lines.forEach((line, index) => {
      const lineNumber = index + 1;
      const importRegex = /from\s+["']([^"']+)["']|require\(\s*["']([^"']+)["']\s*\)|import\(\s*["']([^"']+)["']\s*\)/g;
      let match;

      while ((match = importRegex.exec(line)) !== null) {
        const importPath = match[1] || match[2] || match[3];
        if (resolvesToSharedOutsidePortal(importPath, filePath)) {
          violations.push({
            filePath,
            lineNumber,
            importPath,
          });
        }
      }
    });
  }

  if (violations.length > 0) {
    console.error("Invalid shared imports detected in portal sources:");
    for (const violation of violations) {
      const relativePath = path.relative(portalRoot, violation.filePath);
      console.error(`- ${relativePath}:${violation.lineNumber} ${violation.importPath}`);
    }
    process.exit(1);
  }

  console.log("Shared import check passed.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
