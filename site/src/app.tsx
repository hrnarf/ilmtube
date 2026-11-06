import { useEffect, useState } from "preact/hooks";
import { Footer, Header } from "./components";
import { DataCtx } from "./ctx";
import { loadData, type Data } from "./lib/data";
import { useRoute } from "./lib/router";
import { Home, Search, SeriesPage, Shorts, Speaker, Topic, Topics, Watch } from "./pages";

export function App() {
  const route = useRoute();
  const [data, setData] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { loadData().then(setData).catch((e) => setErr(String(e))); }, []);
  const q = route.path[0] === "search" ? route.query.get("q") ?? "" : "";
  let page;
  switch (route.path[0]) {
    case "search": page = <Search route={route} />; break;
    case "topics": page = <Topics />; break;
    case "topic": page = <Topic route={route} />; break;
    case "speaker": page = <Speaker route={route} />; break;
    case "series": page = <SeriesPage route={route} />; break;
    case "watch": page = <Watch route={route} />; break;
    case "shorts": page = <Shorts route={route} />; break;
    default: page = <Home />;
  }
  return (
    <>
      <Header q={q} />
      {err ? <main><p class="empty">Couldn't load the library: {err}</p></main> : !data ? <main><p class="empty">Loading…</p></main> : <DataCtx.Provider value={data}>{page}</DataCtx.Provider>}
      {data && <Footer />}
    </>
  );
}
