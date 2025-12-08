export type RunEvent =
  | { type: "connected" }
  | { type: "created" | "updated"; run: any }
  | { error?: string; [key: string]: any };

import { API_BASE } from "./api";

export const connectSSE = (runId: string, token: string, onEvent: (e: RunEvent) => void) => {
  const base = API_BASE.endsWith("/") ? API_BASE : `${API_BASE}/`;
  const url = new URL(`runs/${runId}/stream`, base);
  url.searchParams.set("token", token);
  const es = new EventSource(url.toString(), { withCredentials: false });
  es.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      onEvent(data);
    } catch {
      // ignore
    }
  };
  es.onerror = () => {
    es.close();
  };
  return es;
};

export const connectWS = (runId: string, token: string, onEvent: (e: RunEvent) => void) => {
  const base = API_BASE.endsWith("/") ? API_BASE : `${API_BASE}/`;
  const url = new URL(`runs/${runId}/ws`, base.replace(/^http/, "ws"));
  url.searchParams.set("token", token);
  const ws = new WebSocket(url.toString());
  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      onEvent(data);
    } catch {
      // ignore
    }
  };
  ws.onerror = () => {
    ws.close();
  };
  return ws;
};
