#!/usr/bin/env node
/**
 * Minimal UI smoke: login → circuits → open create modal.
 * Requires: npx playwright install chromium (once)
 */
import { chromium } from "playwright";

const BASE = process.env.SMOKE_BASE || "http://127.0.0.1:4173";
const USER = process.env.BUGIS_DEMO_USER || "admin";
const PASS = process.env.BUGIS_DEMO_PASS || "admin123";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
    await page.fill('input[id="username"], input[name="username"], input[placeholder*="用户"]', USER);
    await page.fill('input[type="password"]', PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(?!login)/, { timeout: 15000 });

    await page.goto(`${BASE}/circuits`, { waitUntil: "networkidle", timeout: 30000 });
    await page.getByRole("button", { name: /新建专线/ }).click();
    await page.waitForSelector(".ant-modal", { state: "visible", timeout: 10000 });
    const title = await page.locator(".ant-modal-title").first().textContent();
    if (!title?.includes("专线")) {
      throw new Error(`Unexpected modal title: ${title}`);
    }
    console.log("OK — circuits create modal opens");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("FAIL — frontend smoke:", err.message || err);
  process.exit(1);
});
