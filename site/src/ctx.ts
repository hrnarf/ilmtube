import { createContext } from "preact";
import { useContext } from "preact/hooks";
import type { Data } from "./lib/data";

export const DataCtx = createContext<Data>(null as unknown as Data);
export const useData = () => useContext(DataCtx);
