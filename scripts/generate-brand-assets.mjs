#!/usr/bin/env node
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const repoRoot = resolve(process.cwd());
const svgPath = resolve(repoRoot, "frontends/shared/brand/assets/neft-platform-mark.svg");

const targets = [
  { name: "admin-ui", base: "frontends/admin-ui/public" },
  { name: "client-portal", base: "frontends/client-portal/public" },
  { name: "partner-portal", base: "frontends/partner-portal/public" },
];

const run = (command) => {
  execSync(command, { stdio: "inherit" });
};

const ensureDir = (path) => {
  mkdirSync(path, { recursive: true });
};

const toPng = (outputPath, size) => {
  run(`npx --yes sharp-cli -i "${svgPath}" -o "${outputPath}" -w ${size} -h ${size}`);
};

const toFavicon = (inputPng, outputIco) => {
  run(`npx --yes png-to-ico "${inputPng}" > "${outputIco}"`);
};

for (const target of targets) {
  const brandDir = resolve(repoRoot, target.base, "brand");
  ensureDir(brandDir);

  const brandPng = resolve(brandDir, "neft-platform-mark.png");
  toPng(brandPng, 512);

  if (target.name === "client-portal") {
    toPng(resolve(brandDir, "neft-platform-mark-192.png"), 192);
    toPng(resolve(brandDir, "neft-platform-mark-512.png"), 512);
  }

  toFavicon(brandPng, resolve(repoRoot, target.base, "favicon.ico"));
}
