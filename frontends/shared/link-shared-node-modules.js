const fs = require("node:fs");
const path = require("node:path");

const appRoot = process.cwd();
const frontendsRoot = path.resolve(appRoot, "..");
const sharedRoot = path.join(frontendsRoot, "shared");
const linkPath = path.join(sharedRoot, "node_modules");
const targetPath = path.join(appRoot, "node_modules");

const ensureLink = () => {
  try {
    const stat = fs.lstatSync(linkPath);
    if (stat.isSymbolicLink()) {
      const existingTarget = fs.readlinkSync(linkPath);
      if (path.resolve(frontendsRoot, existingTarget) === targetPath) {
        return;
      }
      fs.unlinkSync(linkPath);
    } else {
      return;
    }
  } catch (error) {
    if (error.code !== "ENOENT") {
      throw error;
    }
  }

  fs.mkdirSync(sharedRoot, { recursive: true });
  fs.symlinkSync(targetPath, linkPath, "dir");
};

ensureLink();
