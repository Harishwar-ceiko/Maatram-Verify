// Downloads the three faces once so the app runs offline during a demo.
// Re-run only if the type system changes.
import { mkdir, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36";

const url =
  "https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;0,6..72,700;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap";

const css = await fetch(url, { headers: { "user-agent": UA } }).then((r) => r.text());
const urls = [...new Set([...css.matchAll(/url\((https:\/\/fonts\.gstatic\.com\/[^)]+)\)/g)].map((m) => m[1]))];

await mkdir(join("public", "fonts"), { recursive: true });
for (const remote of urls) {
  const name = basename(remote);
  const bytes = new Uint8Array(await fetch(remote).then((r) => r.arrayBuffer()));
  await writeFile(join("public", "fonts", name), bytes);
  console.log(`saved ${name} (${bytes.length} bytes)`);
}

const local = urls.reduce((acc, remote) => acc.replaceAll(remote, `/fonts/${basename(remote)}`), css);
await writeFile(join("src", "styles", "fonts.css"), local, "utf8");
console.log(`fonts.css written with ${urls.length} faces`);
