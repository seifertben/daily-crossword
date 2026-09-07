// Generates public/sitemap.xml from the static puzzle files in public/puzzles/.
// The homepage + every /puzzles/YYYY-MM-DD route is listed, newest first.
import { readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PUZZLES_DIR = join(ROOT, "public", "puzzles");
const OUT = join(ROOT, "public", "sitemap.xml");

const BASE = "https://playdailycrossword.com";

function collectDates(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    if (!/^\d{4}-\d{2}-\d{2}\.json$/.test(name)) continue;
    out.push(name.replace(/\.json$/, ""));
  }
  return out.sort().reverse();
}

function lastmodFor(date) {
  // Use a stable last-modified: the day after the puzzle as new content.
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

const dates = collectDates(PUZZLES_DIR);
const urls = [
  `<url><loc>${BASE}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>`,
  ...dates.map(
    (date) =>
      `<url><loc>${BASE}/puzzles/${date}</loc><lastmod>${lastmodFor(date)}</lastmod><changefreq>never</changefreq><priority>0.6</priority></url>`,
  ),
];

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join("\n")}
</urlset>
`;

writeFileSync(OUT, xml.trim() + "\n");
console.log(`Wrote sitemap.xml with ${dates.length + 1} URLs`);
