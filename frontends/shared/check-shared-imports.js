const { readdir, readFile, access } = require("node:fs/promises");
const path = require("node:path");

const portalRoot = process.cwd();
const portalSrc = path.resolve(portalRoot, "src");
const sourceExtensions = new Set([".ts", ".tsx", ".js", ".jsx", ".css", ".scss"]);

async function collectSourceFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectSourceFiles(fullPath));
      continue;
    }
    if (entry.isFile() && sourceExtensions.has(path.extname(fullPath))) {
      files.push(fullPath);
    }
  }

  return files;
}

async function main() {
  try {
    await access(portalSrc);
  } catch (error) {
    console.error(`Cannot find src directory: ${portalSrc}`);
    process.exit(1);
  }

  const files = await collectSourceFiles(portalSrc);
  const violations = [];
  const sharedImportRegex =
    /(?:import\s+["'][^"']*(?:\.\.\/){1,3}shared\/[^"']*["']|from\s+["'][^"']*(?:\.\.\/){1,3}shared\/[^"']*["']|require\(\s*["'][^"']*(?:\.\.\/){1,3}shared\/[^"']*["']\s*\)|@import\s+["'][^"']*(?:\.\.\/){1,3}shared\/[^"']*["'])/g;

  for (const filePath of files) {
    const contents = await readFile(filePath, "utf8");
    const lines = contents.split(/\r?\n/);

    lines.forEach((line, index) => {
      const lineNumber = index + 1;
      let match;

      sharedImportRegex.lastIndex = 0;
      while ((match = sharedImportRegex.exec(line)) !== null) {
        violations.push({
          filePath,
          lineNumber,
          matchedText: match[0],
        });
      }
    });
  }

  if (violations.length > 0) {
    console.error("Invalid shared imports detected in portal sources:");
    for (const violation of violations) {
      const relativePath = path.relative(portalRoot, violation.filePath);
      console.error(`${relativePath}:${violation.lineNumber}: ${violation.matchedText}`);
    }
    process.exit(1);
  }

  console.log("Shared import check passed.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
