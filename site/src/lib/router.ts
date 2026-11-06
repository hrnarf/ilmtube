import { useEffect, useState } from "preact/hooks";

export interface Route { path: string[]; query: URLSearchParams }
function parse(): Route {
  const h = location.hash.replace(/^#/, "") || "/";
  const [p, q = ""] = h.split("?");
  return { path: p.split("/").filter(Boolean).map(decodeURIComponent), query: new URLSearchParams(q) };
}
export function useRoute(): Route {
  const [r, setR] = useState(parse);
  useEffect(() => {
    const on = () => { setR(parse()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}
export const href = (path: string, q?: Record<string, string | undefined>) => {
  const qs = q ? new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]).toString() : "";
  return `#${path}${qs ? `?${qs}` : ""}`;
};
export const go = (path: string, q?: Record<string, string | undefined>) => { location.hash = href(path, q).slice(1); };
