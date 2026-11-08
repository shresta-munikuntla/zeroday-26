import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import assert from "node:assert/strict";
const root = fileURLToPath(new URL("../..", import.meta.url)).replace(
  /\/$/,
  "",
);
const port = process.env.SENTINEL_E2E_PORT || "8003";
const apiBase = `http://127.0.0.1:${port}`;
let occupied = false;
try {
  await fetch(apiBase + "/api/health");
  occupied = true;
} catch {
  /* Expected: fixture port is free. */
}
if (occupied)
  throw new Error(
    "Fixture port is already occupied; choose a free SENTINEL_E2E_PORT",
  );
const server = spawn(
  root + "/.venv/bin/python",
  ["-m", "backend.tests.run_browser_backend"],
  {
    cwd: root,
    env: { ...process.env, SENTINEL_E2E_PORT: port },
    stdio: "ignore",
  },
);
let ready = false;
for (let n = 0; n < 240; n++) {
  try {
    const response = await fetch(apiBase + "/api/health");
    if (response.ok) {
      ready = true;
      break;
    }
  } catch {
    /* Backend may still be starting. */
  }
  await new Promise((r) => setTimeout(r, 250));
}
if (!ready) {
  server.kill("SIGTERM");
  throw new Error("Isolated browser backend did not start");
}
const fixtureServers = [server];
const env = Object.fromEntries(
  readFileSync(root + "/.env", "utf8")
    .split("\n")
    .filter((l) => l && !l.trim().startsWith("#") && l.includes("="))
    .map((l) => {
      const i = l.indexOf("=");
      return [
        l.slice(0, i).trim(),
        l
          .slice(i + 1)
          .trim()
          .replace(/^['"]|['"]$/g, ""),
      ];
    }),
);
const artifacts = root + "/.cache/validation";
mkdirSync(artifacts, { recursive: true });
const chrome =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browser = await chromium.launch({
  ...(existsSync(chrome) ? { executablePath: chrome } : {}),
  headless: true,
});
const results = { checks: [], javascriptErrors: [], unexpectedResponses: [] };
const pass = (name) => {
  results.checks.push({ name, status: "PASS" });
  console.log("PASS", name);
};
async function start(user = "reviewer", isolated = true, origin = apiBase) {
  const context = await browser.newContext({
    viewport: { width: 1512, height: 1100 },
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => results.javascriptErrors.push(e.message));
  if (isolated)
    await page.route("http://localhost:8001/api/**", (r) =>
      r.continue({
        url: r.request().url().replace("http://localhost:8001", origin),
      }),
    );
  await page.goto("http://localhost:5173");
  await page.getByLabel("Username", { exact: true }).fill(user);
  await page
    .getByLabel("Password", { exact: true })
    .fill(
      env[
        user === "reviewer" ? "DEMO_REVIEWER_PASSWORD" : "DEMO_VIEWER_PASSWORD"
      ],
    );
  await page.getByRole("button", { name: /Sign in/ }).click();
  await page
    .getByRole("heading", { name: "INC-001", exact: true })
    .waitFor({ timeout: 30000 });
  return { context, page };
}
async function tab(page, name) {
  await page.getByRole("tab", { name: new RegExp(name) }).click();
}
async function api(page, path, method = "get", data) {
  const token = await page.evaluate(() =>
    sessionStorage.getItem("sentinel_token"),
  );
  return page.request[method](apiBase + "/api" + path, {
    headers: { Authorization: "Bearer " + token },
    data,
  });
}
try {
  const { context, page } = await start();
  pass("Reviewer login and actual backend connection");
  await page.getByText("Backend connected", { exact: true }).waitFor();
  assert.equal(await page.locator(".incident-item").count(), 1);
  assert.ok(
    (await page.locator(".incident-item-bottom").innerText())
      .toLowerCase()
      .includes("3 assets"),
  );
  pass("Overview/incident list populated from real detail API");
  await page.getByLabel("Search incidents").fill("does-not-match");
  assert.equal(await page.locator(".incident-item").count(), 0);
  await page.getByLabel("Search incidents").fill("INC-001");
  assert.equal(await page.locator(".incident-item").count(), 1);
  await page.getByLabel("Search incidents").fill("");
  pass("Incident search filters without changing the selected report");
  for (const text of ["R1", "R2", "R4", "LOG-101"])
    assert.ok((await page.locator("#agent-panel").innerText()).includes(text));
  pass("Detection fields and triggered rules displayed");
  await page.locator(".disclosure").first().locator("summary").click();
  assert.ok(
    (await page.locator(".disclosure").first().innerText()).includes(
      "Successful login",
    ),
  );
  pass("Expandable backend rule explanation");
  await tab(page, "Investigate");
  assert.equal(await page.locator(".event-timeline li").count(), 5);
  for (const text of ["Authorized", "Expired", "No permission", "90%"])
    assert.ok((await page.locator("#agent-panel").innerText()).includes(text));
  await page
    .locator(".asset-selector")
    .getByRole("button", { name: /identity-sync/ })
    .click();
  assert.ok(
    (await page.locator(".asset-detail").innerText()).includes("PERM-003"),
  );
  pass("Timeline, confidence and asset permission inspector");
  await tab(page, "Intelligence");
  assert.ok(
    (await page.locator("#agent-panel").innerText()).includes(
      "Source-only fallback",
    ),
  );
  await page
    .getByRole("button", { name: "Test Nemotron", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Test Nemotron", exact: true })
    .waitFor();
  assert.ok(
    (await page.locator("#agent-panel").innerText()).includes(
      "No API key configured",
    ),
  );
  pass("Explicit no-key connection result without false success");
  const before = await (await api(page, "/incidents/INC-001")).json();
  await page
    .getByRole("button", { name: "Generate AI Preview", exact: true })
    .click();
  await page
    .getByText("FRESH AI PREVIEW", { exact: true })
    .waitFor({ timeout: 30000 });
  const after = await (await api(page, "/incidents/INC-001")).json();
  assert.deepEqual(after.intelligence, before.intelligence);
  assert.deepEqual(after.recipients, before.recipients);
  assert.equal(after.approval_status, before.approval_status);
  pass("Fresh preview leaves saved report, drafts and approval unchanged");
  await page
    .getByRole("button", { name: "Show saved report", exact: true })
    .click();
  await page.getByText("SAVED INTELLIGENCE", { exact: true }).waitFor();
  assert.equal(
    await page.getByText("FRESH AI PREVIEW", { exact: true }).count(),
    0,
  );
  pass("Preview can be dismissed to return to saved intelligence");
  const expandActions = page.getByRole("button", {
    name: /^Show all \d+ actions$/,
  });
  if (await expandActions.count()) {
    assert.equal(await page.locator(".recommendations li").count(), 3);
    await expandActions.click();
    assert.ok((await page.locator(".recommendations li").count()) > 3);
    await page
      .getByRole("button", { name: "Show fewer actions", exact: true })
      .click();
    pass("Long recommendation sets expand without hiding the returned total");
  }
  const citation = page
    .locator(".recommendations .citation-buttons button")
    .first();
  assert.ok(
    await citation.count(),
    "Expected indexed demo guidance with citations",
  );
  await citation.click();
  assert.ok(await page.locator(".source-detail[open]").count());
  pass("Citation click opens actual reference summary");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: artifacts + "/redesign-intelligence-desktop.png",
    fullPage: true,
  });
  await tab(page, "Validate");
  assert.ok((await page.locator(".validation-list>div").count()) >= 5);
  assert.ok((await page.locator(".audit-history details").count()) >= 14);
  pass("Validation checklist and persisted audit details");
  await tab(page, "Notify");
  assert.equal(await page.locator(".message-disclosure").count(), 3);
  await page.locator(".message-disclosure").first().locator("summary").click();
  assert.ok(
    (await page.locator(".message-body").first().innerText()).includes(
      "INC-001",
    ),
  );
  pass("Three owner-specific notification previews");
  assert.equal(
    (await api(page, "/incidents/INC-001/send", "post", {})).status(),
    409,
  );
  assert.equal(
    await page.getByRole("button", { name: /Send notifications/ }).count(),
    0,
  );
  pass("Sending blocked before approval by API and UI");
  await page
    .getByRole("button", { name: "Approve incident", exact: true })
    .click();
  await page.getByRole("alertdialog").waitFor();
  await page.keyboard.press("Escape");
  assert.equal(await page.getByRole("alertdialog").count(), 0);
  pass("Confirmation dialog supports Escape/cancel");
  await page
    .getByRole("button", { name: "Approve incident", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm approve", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Send notifications (3)", exact: true })
    .waitFor();
  await page.getByRole("button", { name: "Run Demo", exact: true }).click();
  await page.locator(".nav-actions button.primary:not([disabled])").waitFor();
  await tab(page, "Notify");
  await page
    .getByRole("button", { name: "Send notifications (3)", exact: true })
    .waitFor();
  assert.equal(await page.locator(".incident-item").count(), 1);
  pass("Rerun deduplicates and preserves approval");
  await page
    .getByRole("button", { name: "Send notifications (3)", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm send", exact: true }).click();
  await page
    .getByText("Mock sent · simulated", { exact: true })
    .first()
    .waitFor();
  assert.equal(
    await page.getByText("Mock sent · simulated", { exact: true }).count(),
    3,
  );
  assert.equal(
    (await api(page, "/incidents/INC-001/send", "post", {})).status(),
    409,
  );
  pass("Approved mock sending labelled simulated; repeat send rejected");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: artifacts + "/redesign-notifications-desktop.png",
    fullPage: true,
  });
  await page.getByRole("tab", { name: /Detect/ }).focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(
    await page
      .getByRole("tab", { name: /Investigate/ })
      .getAttribute("aria-selected"),
    "true",
  );
  pass("Workflow keyboard arrow navigation");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const stage of [
    "Detect",
    "Investigate",
    "Intelligence",
    "Validate",
    "Notify",
  ]) {
    await tab(page, stage);
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      stage + " overflow",
    );
  }
  pass("All agent views fit 390px mobile viewport");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: artifacts + "/redesign-mobile.png",
    fullPage: true,
  });
  await context.close();
  const edge = await start();
  await tab(edge.page, "Intelligence");
  let release;
  const hold = new Promise((resolve) => {
    release = resolve;
  });
  await edge.page.route("**/preview-intelligence", async (route) => {
    await hold;
    await route.fulfill({
      json: {
        mode: "fallback",
        model: null,
        intelligence: {
          matched_techniques: [],
          policy_references: [],
          historical_cases: [],
          recommended_actions: [],
          recommended_resources: [],
          limitations: ["No relevant source was retrieved."],
        },
        document_ids: [],
      },
    });
  });
  await edge.page
    .getByRole("button", { name: "Generate AI Preview", exact: true })
    .click();
  await edge.page
    .getByText(
      "Retrieving relevant knowledge and requesting structured guidance",
      { exact: true },
    )
    .waitFor();
  pass(
    "Loading state remains explicit while preview request is pending (test-controlled delay)",
  );
  release();
  await edge.page
    .getByText("No sourced recommendation available", { exact: true })
    .waitFor();
  assert.ok(
    (await edge.page.locator("#agent-panel").innerText()).includes(
      "No relevant sources retrieved",
    ),
  );
  pass(
    "No-source contract displays empty guidance without invented citations (UI response stub)",
  );
  await edge.page.unroute("**/preview-intelligence");
  await edge.page.route("**/api/ai/check", (route) =>
    route.fulfill({
      status: 403,
      json: { detail: "Reviewer access is required for this action." },
    }),
  );
  await edge.page
    .getByRole("button", { name: "Test Nemotron", exact: true })
    .click();
  await edge.page
    .getByRole("alert")
    .filter({ hasText: "Reviewer access is required" })
    .waitFor();
  pass("Model authorization error is visible (UI error-response stub)");
  await edge.page.unroute("**/api/ai/check");
  await edge.page.evaluate(() => {
    window.print = () => {
      window.__printInvoked = true;
    };
  });
  await edge.page
    .getByRole("button", { name: "Export report", exact: true })
    .click();
  assert.equal(await edge.page.evaluate(() => window.__printInvoked), true);
  pass("Export invokes browser print action");
  await edge.page.route("**/api/health", (route) => route.abort());
  await edge.page
    .getByRole("button", { name: "Refresh dashboard", exact: true })
    .click();
  await edge.page.getByText("Backend unavailable", { exact: true }).waitFor();
  pass(
    "Unavailable backend health state displayed (intentional network abort)",
  );
  await edge.page.unroute("**/api/health");
  await edge.page.route("**/api/incidents", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Incident service temporarily unavailable." },
    }),
  );
  await edge.page
    .getByRole("button", { name: "Refresh dashboard", exact: true })
    .click();
  await edge.page
    .getByRole("alert")
    .filter({ hasText: "Incident service temporarily unavailable." })
    .waitFor();
  pass(
    "API failure shown while retaining last saved data (UI error-response stub)",
  );
  await edge.page.unroute("**/api/incidents");
  await edge.page.route("**/api/incidents", (route) =>
    route.fulfill({ json: [] }),
  );
  await edge.page
    .getByRole("button", { name: "Refresh dashboard", exact: true })
    .click();
  await edge.page.getByText("No incident selected", { exact: true }).waitFor();
  assert.equal(await edge.page.locator(".incident-item").count(), 0);
  pass("Empty incident collection has clear empty state (UI response stub)");
  await edge.context.close();
  const viewer = await start("viewer");
  await tab(viewer.page, "Notify");
  assert.equal(
    await viewer.page
      .getByRole("button", { name: "Approve incident", exact: true })
      .count(),
    0,
  );
  assert.equal(
    (await api(viewer.page, "/incidents/INC-001/approve", "post", {})).status(),
    403,
  );
  await tab(viewer.page, "Intelligence");
  assert.ok(
    await viewer.page
      .getByRole("button", { name: "Test Nemotron", exact: true })
      .isDisabled(),
  );
  pass("Viewer controls and backend reviewer authorization");
  await viewer.page
    .getByRole("button", { name: "Sign out", exact: true })
    .click();
  await viewer.page
    .getByRole("heading", { name: "Incident desk", exact: true })
    .waitFor();
  assert.equal(
    await viewer.page.evaluate(() => sessionStorage.getItem("sentinel_token")),
    null,
  );
  pass("Sign out clears the browser authentication token");
  await viewer.context.close();
  const rejectPort = String(Number(port) + 1);
  const rejectBase = `http://127.0.0.1:${rejectPort}`;
  let rejectOccupied = false;
  try {
    await fetch(rejectBase + "/api/health");
    rejectOccupied = true;
  } catch {
    /* Dedicated fixture port must be free. */
  }
  assert.equal(rejectOccupied, false, "Rejection fixture port is occupied");
  const rejectServer = spawn(
    root + "/.venv/bin/python",
    ["-m", "backend.tests.run_browser_backend"],
    {
      cwd: root,
      env: { ...process.env, SENTINEL_E2E_PORT: rejectPort },
      stdio: "ignore",
    },
  );
  fixtureServers.push(rejectServer);
  let rejectionReady = false;
  for (let n = 0; n < 240; n++) {
    try {
      if ((await fetch(rejectBase + "/api/health")).ok) {
        rejectionReady = true;
        break;
      }
    } catch {
      /* Starting fixture. */
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  assert.ok(rejectionReady, "Rejection fixture failed to start");
  const rejectCase = await start("reviewer", true, rejectBase);
  await tab(rejectCase.page, "Notify");
  await rejectCase.page
    .getByRole("button", { name: "Reject incident", exact: true })
    .click();
  await rejectCase.page
    .getByRole("button", { name: "Confirm reject", exact: true })
    .click();
  await rejectCase.page
    .getByRole("heading", { name: "Notifications rejected", exact: true })
    .waitFor();
  assert.equal(
    await rejectCase.page
      .getByRole("button", { name: /Send notifications/ })
      .count(),
    0,
  );
  pass(
    "Confirmed rejection persists and removes delivery actions on a separate real fixture",
  );
  await rejectCase.context.close();
  const legacy = await start("reviewer", false);
  await tab(legacy.page, "Investigate");
  assert.ok(
    (await legacy.page.locator("#agent-panel").innerText()).includes(
      "Timeline not recorded",
    ),
  );
  await tab(legacy.page, "Notify");
  assert.ok(
    (await legacy.page.locator("#agent-panel").innerText()).includes(
      "Notifications rejected",
    ),
  );
  pass("Legacy missing fields labelled; rejected decision preserved");
  await legacy.context.close();
  assert.deepEqual(results.javascriptErrors, []);
  pass("No browser JavaScript errors");
} catch (e) {
  results.failure = e.message;
  console.error(e.stack);
  process.exitCode = 1;
} finally {
  writeFileSync(
    artifacts + "/redesign-browser-results.json",
    JSON.stringify(results, null, 2),
  );
  await browser.close();
  for (const fixture of fixtureServers) fixture.kill("SIGTERM");
}
