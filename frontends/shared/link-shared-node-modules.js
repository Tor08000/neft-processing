const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const appRoot = process.cwd();
const frontendsRoot = path.resolve(appRoot, "..");
const sharedRoot = path.join(frontendsRoot, "shared");
const linkPath = path.join(sharedRoot, "node_modules");
const targetPath = path.join(appRoot, "node_modules");
const isWindows = process.platform === "win32";

const normalizeExistingTarget = (existingTarget) => {
  if (path.isAbsolute(existingTarget)) {
    return path.resolve(existingTarget);
  }
  return path.resolve(path.dirname(linkPath), existingTarget);
};

const removeExistingIfInvalid = () => {
  try {
    const stat = fs.lstatSync(linkPath);
    if (stat.isSymbolicLink()) {
      const existingTarget = fs.readlinkSync(linkPath);
      if (normalizeExistingTarget(existingTarget) === path.resolve(targetPath)) {
        return false;
      }
      fs.unlinkSync(linkPath);
      return true;
    }

    if (isWindows && stat.isDirectory()) {
      const realPath = fs.realpathSync(linkPath);
      if (path.resolve(realPath) === path.resolve(targetPath)) {
        return false;
      }
      fs.rmSync(linkPath, { recursive: true, force: true });
      return true;
    }

    return false;
  } catch (error) {
    if (error.code === "ENOENT") {
      return true;
    }
    throw error;
  }
};

const warnWindowsSkip = (error) => {
  console.warn("Shared node_modules linking skipped on Windows (no privileges).");
  if (error) {
    console.warn(`Reason: ${error.message}`);
  }
};

const tryCreateWindowsJunction = () => {
  try {
    fs.symlinkSync(targetPath, linkPath, "junction");
    return true;
  } catch (error) {
    const command = `mklink /J "${linkPath}" "${targetPath}"`;
    const result = spawnSync("cmd", ["/c", command], { stdio: "pipe" });
    if (result.status === 0) {
      return true;
    }

    const details = (result.stderr || result.stdout || "").toString().trim();
    const fallbackError = new Error(details || "mklink /J failed");
    fallbackError.code = error.code || "MKLINK_FAILED";
    throw fallbackError;
  }
};

const ensureLink = () => {
  const shouldCreate = removeExistingIfInvalid();
  if (!shouldCreate) {
    return;
  }

  fs.mkdirSync(sharedRoot, { recursive: true });

  try {
    fs.symlinkSync(targetPath, linkPath, "dir");
    return;
  } catch (error) {
    if (!isWindows || !["EPERM", "EACCES"].includes(error.code)) {
      throw error;
    }
  }

  try {
    tryCreateWindowsJunction();
  } catch (error) {
    warnWindowsSkip(error);
  }
};

ensureLink();
