import type {
  DownloadJobResponse,
  HealthResponse,
  SessionResponse,
  TagCatalogResponse,
  TagDefinition,
  TrackResponse,
} from "../types/music";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export function resolveApiUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
  });

  if (!res.ok) {
    let detail = `Error HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      if (typeof errBody?.detail === "string") {
        detail = errBody.detail;
      }
    } catch {
      // ignore non-json error bodies
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/v1/health");
}

export function getTagCatalog(): Promise<TagCatalogResponse> {
  return requestJson<TagCatalogResponse>("/api/v1/tags/catalog");
}

export function createCustomTag(
  category: "language" | "mood",
  name: string,
): Promise<{ tag: TagDefinition; catalog: TagCatalogResponse }> {
  return requestJson("/api/v1/tags/catalog", {
    method: "POST",
    body: JSON.stringify({ category, name }),
  });
}

export function analyzeUrl(url: string, signal?: AbortSignal): Promise<SessionResponse> {
  return requestJson<SessionResponse>("/api/v1/analyze", {
    method: "POST",
    body: JSON.stringify({ url }),
    signal,
  });
}

export function getSession(sessionId: string): Promise<SessionResponse> {
  return requestJson<SessionResponse>(`/api/v1/sessions/${sessionId}`);
}

export function processTrack(
  sessionId: string,
  trackId: string,
  force = false,
  signal?: AbortSignal,
): Promise<TrackResponse> {
  const qs = force ? "?force=true" : "";
  return requestJson<TrackResponse>(
    `/api/v1/sessions/${sessionId}/tracks/${trackId}/process${qs}`,
    { method: "POST", signal },
  );
}

export function updateTrackMetadata(
  sessionId: string,
  trackId: string,
  payload: {
    title?: string;
    artists?: string[];
    artists_text?: string;
    album?: string;
    selected_artwork_id?: string;
  },
): Promise<TrackResponse> {
  return requestJson<TrackResponse>(
    `/api/v1/sessions/${sessionId}/tracks/${trackId}/metadata`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function applyMetadataCandidate(
  sessionId: string,
  trackId: string,
  source: string,
  fields?: string[],
): Promise<TrackResponse> {
  return requestJson<TrackResponse>(
    `/api/v1/sessions/${sessionId}/tracks/${trackId}/apply-candidate`,
    {
      method: "POST",
      body: JSON.stringify({ source, fields }),
    },
  );
}

export function refreshArtworkSearch(
  sessionId: string,
  trackId: string,
): Promise<TrackResponse> {
  return requestJson<TrackResponse>(
    `/api/v1/sessions/${sessionId}/tracks/${trackId}/artwork/search`,
    { method: "POST" },
  );
}

export function uploadCustomArtwork(
  sessionId: string,
  trackId: string,
  file: File,
): Promise<TrackResponse> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<TrackResponse>(
    `/api/v1/sessions/${sessionId}/tracks/${trackId}/artwork/upload`,
    {
      method: "POST",
      body: form,
    },
  );
}

export function updateTrackTags(
  sessionId: string,
  trackId: string,
  tagIds: string[],
): Promise<TrackResponse> {
  return requestJson<TrackResponse>(
    `/api/v1/sessions/${sessionId}/tracks/${trackId}/tags`,
    {
      method: "PUT",
      body: JSON.stringify({ tag_ids: tagIds }),
    },
  );
}

export function clearQueue(sessionId: string): Promise<SessionResponse> {
  return requestJson<SessionResponse>(`/api/v1/sessions/${sessionId}/queue`, {
    method: "DELETE",
  });
}

export function removeFromQueue(
  sessionId: string,
  trackId: string,
): Promise<SessionResponse> {
  return requestJson<SessionResponse>(`/api/v1/sessions/${sessionId}/queue/${trackId}`, {
    method: "DELETE",
  });
}

export function restoreToQueue(
  sessionId: string,
  trackId: string,
): Promise<SessionResponse> {
  return requestJson<SessionResponse>(`/api/v1/sessions/${sessionId}/queue/${trackId}`, {
    method: "POST",
  });
}

export function startSingleDownload(
  sessionId: string,
  trackId: string,
): Promise<DownloadJobResponse> {
  return requestJson<DownloadJobResponse>(
    `/api/v1/sessions/${sessionId}/tracks/${trackId}/download`,
    { method: "POST" },
  );
}

export function startPlaylistDownload(sessionId: string): Promise<DownloadJobResponse> {
  return requestJson<DownloadJobResponse>(
    `/api/v1/sessions/${sessionId}/download-playlist`,
    { method: "POST" },
  );
}

export function cancelDownloadJob(jobId: string): Promise<DownloadJobResponse> {
  return requestJson<DownloadJobResponse>(`/api/v1/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export function subscribeToJobEvents(
  jobId: string,
  onUpdate: (job: DownloadJobResponse) => void,
  onError?: () => void,
): () => void {
  const source = new EventSource(`${API_BASE}/api/v1/jobs/${jobId}/events`);
  source.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data) as DownloadJobResponse;
      onUpdate(parsed);
      if (["completed", "failed", "cancelled"].includes(parsed.status)) {
        source.close();
      }
    } catch {
      // ignore malformed keepalive
    }
  };
  source.onerror = () => {
    source.close();
    onError?.();
  };
  return () => source.close();
}
