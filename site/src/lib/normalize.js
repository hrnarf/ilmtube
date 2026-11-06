// Shared by the browser app and the Node index builder. Pure ESM, no imports.
export function normalizeText(s) {
  return String(s ?? "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/['’`ʻʿ]/g, "")
    .replace(/[-_]/g, " ")
    .replace(/[^a-z0-9؀-ۿ ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** groups: array of arrays of terms; first term of each group is the canonical form. */
export function buildSynonyms(groups) {
  const pairs = [];
  for (const g of groups) {
    const canon = normalizeText(g[0]);
    for (const t of g.slice(1)) {
      const n = normalizeText(t);
      if (n && n !== canon) pairs.push([new RegExp(`\\b${n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "g"), canon, n.length]);
    }
  }
  pairs.sort((a, b) => b[2] - a[2]);
  return pairs;
}

export function canonicalize(text, syn) {
  let s = normalizeText(text);
  for (const [re, canon] of syn) s = s.replace(re, canon);
  return s;
}
