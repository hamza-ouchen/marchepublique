const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright-core");

const [mode, input, output] = process.argv.slice(2);
const officialHost = "www.marchespublics.gov.ma";
const maxBytes = 50 * 1024 * 1024;

async function downloadDirect(context, job, folder) {
  const url = new URL(job.url);
  const attachment = url.pathname.match(/^\/bdc\/entreprise\/consultation\/download\/(\d+)\/(\d+)\/?$/);
  if (url.protocol !== "https:" || url.hostname !== officialHost ||
      !attachment || job.id !== "bdc:" + attachment[1]) {
    throw new Error("Unexpected attachment URL");
  }
  const response = await context.request.get(url.href, { timeout: 25000, maxRedirects: 0 });
  try {
    if (!response.ok()) throw new Error("HTTP " + response.status());
    if (Number(response.headers()["content-length"]) > maxBytes) {
      throw new Error("Attachment exceeds 50 MiB");
    }
    const data = await response.body();
    if (data.length > maxBytes) throw new Error("Attachment exceeds 50 MiB");
    const body = data.subarray(0, 48).toString().trimStart();
    if (!data.length || /^<(html|!doctype)|^\s*\{.*error/i.test(body)) {
      throw new Error("Attachment endpoint returned an error page");
    }
    const ext = body.startsWith("%PDF-") ? ".pdf" : body.startsWith("PK") ? ".zip" : ".bin";
    const name = job.id.replaceAll(":", "-") + "-" + attachment[2] + ext;
    await fs.writeFile(path.join(folder, name), data);
    return name;
  } finally {
    await response.dispose();
  }
}

async function downloadViaAOMaroc(context, job, folder) {
  const official = new URL(job.source_url);
  const ref = official.searchParams.get("refConsultation");
  const org = official.searchParams.get("orgAcronyme");
  if (official.hostname.replace(/^www\./, "") !== "marchespublics.gov.ma" ||
      job.id !== "consultation:" + org?.toLowerCase() + ":" + ref) {
    throw new Error("Consultation identity mismatch");
  }
  const pageUrl = new URL("https://www.aomaroc.com/cps");
  pageUrl.search = new URLSearchParams({ org, ref }).toString();
  const page = await context.newPage();
  try {
    const response = await page.goto(pageUrl.href, { waitUntil: "domcontentloaded", timeout: 30000 });
    if (!response?.ok()) throw new Error("HTTP " + response?.status());
    const packageLink = page.getByText(/Tout télécharger/i).first();
    const automationRefusal = page.getByText(/Téléchargement automatique refusé/i).first();
    await packageLink.or(automationRefusal).first().waitFor({ state: "visible", timeout: 180000 });
    if (await automationRefusal.isVisible()) {
      throw new Error("Automated download refused");
    }
    const later = page.getByText(/Plus tard/).first();
    if (await later.isVisible()) await later.click();
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 90000 }),
      packageLink.click({ timeout: 10000 }),
    ]);
    const name = job.id.replaceAll(":", "-") + "-" + path.basename(download.suggestedFilename());
    await download.saveAs(path.join(folder, name));
    return { name, source: pageUrl.href };
  } finally {
    await page.close();
  }
}

async function main() {
  if (!["bdc", "ao-maroc"].includes(mode) || !input || !output) {
    throw new Error("Usage: node download_public_documents.cjs bdc|ao-maroc input.json output-directory");
  }
  const folder = path.resolve(output);
  await fs.mkdir(folder, { recursive: true });
  const manifest = path.join(folder, "download-results.json");
  const source = JSON.parse(await fs.readFile(input, "utf8"));
  const jobs = mode === "bdc"
    ? source.results.flatMap(row => row.files.map(url => ({ id: row.id, source_url: row.url, url })))
    : source.offers.filter(row => row.type !== "bon_de_commande").map(row => ({ ...row, source_url: row.url, url: row.url }));
  const results = new Map();
  try {
    for (const row of JSON.parse(await fs.readFile(manifest, "utf8"))) {
      if (!row.document && /Target page, context or browser has been closed/i.test(row.error || "")) continue;
      results.set(row.url, row);
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const maxAttempts = Number(process.env.DOCUMENT_MAX_ATTEMPTS || 0);
  const now = new Date().toLocaleString("sv-SE", { timeZone: "Africa/Casablanca" }).replace(" ", "T");
  for (const job of jobs) {
    if (mode === "ao-maroc" && job.deadline && job.deadline <= now && !results.get(job.url)?.document) {
      results.set(job.url, { ...results.get(job.url), ...job, error: "Submission deadline passed", expired: true });
    }
  }
  function needsAttempt(job) {
    const previous = results.get(job.url);
    return !job.manualStorageConfirmed && !previous?.document && !previous?.expired &&
      (!maxAttempts || (previous?.attempts ?? 0) < maxAttempts);
  }
  const pending = jobs.filter(needsAttempt).sort(
    (a, b) => (results.get(a.url)?.attempts ?? 0) - (results.get(b.url)?.attempts ?? 0),
  );
  const executablePath = process.env.DOCUMENT_CHROMIUM_PATH;
  const browser = await chromium.launch(executablePath
    ? { executablePath, headless: true }
    : { channel: "msedge", headless: false });
  const seconds = Number(process.env.DOCUMENT_BROWSER_SECONDS || 0);
  let timedOut = false;
  let disconnected = false;
  browser.on("disconnected", () => { disconnected = true; });
  const deadline = seconds > 0 ? setTimeout(() => {
    timedOut = true;
    void browser.close().catch(() => {});
  }, seconds * 1000) : undefined;
  let completed = 0;
  let writes = Promise.resolve();
  function checkpoint() {
    writes = writes.then(async () => {
      await fs.writeFile(manifest + ".tmp", JSON.stringify([...results.values()]));
      await fs.rename(manifest + ".tmp", manifest);
    });
    return writes;
  }
  try {
    const serial = process.env.DOCUMENT_CONCURRENCY === "1";
    const maxWorkers = serial ? 1 : mode === "ao-maroc" ? 20 : 4;
    const contexts = [];
    const resumeWorkers = Number(process.env.DOCUMENT_RESUME_CONCURRENCY);
    let workers = mode === "ao-maroc"
      ? Math.min(maxWorkers, Number.isInteger(resumeWorkers) && resumeWorkers > 0 ? resumeWorkers : maxWorkers)
      : 1;
    console.log(`[${mode}] starting at ${workers} concurrent requests`);
    let fastResults = 0;
    let throttled = false;
    let accessDenied = false;
    const active = new Map();
    async function attempt(job, index) {
      const started = Date.now();
      const attempts = (results.get(job.url)?.attempts ?? 0) + 1;
      if (mode === "ao-maroc" && job.deadline) {
        const now = new Date().toLocaleString("sv-SE", { timeZone: "Africa/Casablanca" }).replace(" ", "T");
        if (job.deadline <= now) {
          results.set(job.url, { ...job, error: "Submission deadline passed", attempts, expired: true });
          return "expired";
        }
      }
      try {
        contexts[index] ??= await browser.newContext({ acceptDownloads: true });
        const context = contexts[index];
        const result = mode === "bdc"
          ? { name: await downloadDirect(context, job, folder), source: job.url }
          : await downloadViaAOMaroc(context, job, folder);
        results.set(job.url, { ...job, document: result.name, document_source: result.source, attempts });
      } catch (error) {
        if (timedOut || disconnected || /Target page, context or browser has been closed/i.test(error.message)) {
          disconnected = true;
          return "interrupted";
        }
        const message = error.message.split("\n")[0];
        if (message === "Automated download refused") {
          accessDenied = true;
          throttled = true;
          return "interrupted";
        }
        results.set(job.url, { ...job, error: message, attempts });
        if (/^HTTP (403|429|503|888)\b/.test(message)) throttled = true;
      }
      completed++;
      if (mode === "ao-maroc" || completed % 25 === 0) {
        await checkpoint();
        console.log(`${completed}/${pending.length} requests (${[...results.values()].filter(row => row.document).length} downloads)`);
      }
      if (!results.get(job.url)?.document) return "failed";
      return Date.now() - started < 45000 ? "fast" : "slow";
    }
    let cursor = 0;
    while (cursor < pending.length || active.size) {
      while (cursor < pending.length && active.size < workers && !timedOut && !disconnected && !throttled) {
        let index = 0;
        while (active.has(index)) index++;
        active.set(index, attempt(pending[cursor++], index).then(outcome => ({ index, outcome })));
      }
      if (!active.size) break;
      const { index, outcome } = await Promise.race(active.values());
      active.delete(index);
      if (outcome === "expired" || outcome === "interrupted") continue;
      const previousWorkers = workers;
      if (outcome === "fast") {
        fastResults++;
        if (fastResults >= workers * (mode === "ao-maroc" ? 1 : 2) && workers < maxWorkers) {
          workers++;
          fastResults = 0;
        }
      } else {
        fastResults = 0;
        if (outcome === "failed" || mode !== "ao-maroc") workers = Math.max(1, workers - 1);
      }
      if (workers !== previousWorkers) console.log(`[${mode}] ${workers} concurrent requests`);
    }
    await checkpoint();
    const downloaded = jobs.filter(job => results.get(job.url)?.document).length;
    const remaining = jobs.filter(needsAttempt).length;
    console.log(JSON.stringify({ requested: jobs.length, downloaded, remaining, timedOut, disconnected, throttled, accessDenied, concurrency: workers }));
  } finally {
    clearTimeout(deadline);
    await browser.close();
  }
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
