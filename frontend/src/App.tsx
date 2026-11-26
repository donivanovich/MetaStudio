import { AlertTriangle, Info, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActionFooter } from "./components/ActionFooter";
import { DownloadProgressDrawer } from "./components/DownloadProgressDrawer";
import { EmptyState } from "./components/EmptyState";
import { HeaderBar } from "./components/HeaderBar";
import { MetadataEditorColumn } from "./components/MetadataEditorColumn";
import { PlayerColumn } from "./components/PlayerColumn";
import { SourcesArtworkColumn } from "./components/SourcesArtworkColumn";
import { TrackNavBar } from "./components/TrackNavBar";
import {
  analyzeUrl,
  applyMetadataCandidate,
  cancelDownloadJob,
  createCustomTag,
  getHealth,
  getSession,
  getTagCatalog,
  processTrack,
  refreshArtworkSearch,
  removeFromQueue,
  resolveApiUrl,
  restoreToQueue,
  startPlaylistDownload,
  startSingleDownload,
  subscribeToJobEvents,
  updateTrackMetadata,
  updateTrackTags,
  uploadCustomArtwork,
} from "./services/api";
import type {
  DownloadJobResponse,
  SessionResponse,
  TagCatalogResponse,
  TrackResponse,
} from "./types/music";

export function App() {
  const [url, setUrl] = useState("");
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [catalog, setCatalog] = useState<TagCatalogResponse | null>(null);
  const [ffmpegAvailable, setFfmpegAvailable] = useState<boolean | null>(null);
  const [spotifyNotice, setSpotifyNotice] = useState<string | null>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [loadingTrackId, setLoadingTrackId] = useState<string | null>(null);
  const [refreshingSearch, setRefreshingSearch] = useState(false);
  const [uploadingArt, setUploadingArt] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<DownloadJobResponse | null>(null);

  const processAbortRef = useRef<AbortController | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const sseCleanupRef = useRef<(() => void) | null>(null);

  const syncHealth = useCallback(() => {
    getHealth()
      .then((h) => {
        setFfmpegAvailable(h.ffmpeg.available);
        setSpotifyNotice(h.spotify_status?.detail ?? null);
      })
      .catch(() => setFfmpegAvailable(null));
  }, []);

  // Load health & versioned tag catalog on startup
  useEffect(() => {
    syncHealth();
    getTagCatalog()
      .then(setCatalog)
      .catch(() => {});

    return () => {
      processAbortRef.current?.abort();
      sseCleanupRef.current?.();
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, [syncHealth]);

  const currentTrack: TrackResponse | null =
    session && session.tracks[currentIndex] ? session.tracks[currentIndex] : null;

  const replaceTrackInSession = useCallback((updated: TrackResponse) => {
    setSession((prev) => {
      if (!prev) return prev;
      const nextTracks = prev.tracks.map((t) => (t.id === updated.id ? updated : t));
      const processed = nextTracks.filter((t) =>
        ["ready", "downloading", "downloaded"].includes(t.status),
      ).length;
      return { ...prev, tracks: nextTracks, processed_tracks: processed };
    });
  }, []);

  const ensureTrackProcessed = useCallback(
    async (sid: string, track: TrackResponse, force = false) => {
      if (!force && (track.status === "ready" || track.status === "downloaded")) return;

      processAbortRef.current?.abort();
      const controller = new AbortController();
      processAbortRef.current = controller;
      setLoadingTrackId(track.id);
      setErrorBanner(null);

      try {
        const enriched = await processTrack(sid, track.id, force, controller.signal);
        replaceTrackInSession(enriched);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setErrorBanner((err as Error).message);
      } finally {
        setLoadingTrackId((curr) => (curr === track.id ? null : curr));
      }
    },
    [replaceTrackInSession],
  );

  const handleAnalyze = async () => {
    if (!url.trim()) return;
    setAnalyzing(true);
    setErrorBanner(null);
    setActiveJob(null);
    sseCleanupRef.current?.();
    processAbortRef.current?.abort();

    try {
      const result = await analyzeUrl(url.trim());
      setSession(result);
      setCurrentIndex(0);
      syncHealth();
    } catch (err) {
      setErrorBanner((err as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSelectIndex = (idx: number) => {
    if (!session || idx < 0 || idx >= session.tracks.length) return;
    setCurrentIndex(idx);
    const target = session.tracks[idx];
    if (target.status === "pending") {
      void ensureTrackProcessed(session.session_id, target);
    }
  };

  // Debounced metadata sync to backend (immediate optimistic UI update!)
  const scheduleMetadataPatch = (
    sid: string,
    trackId: string,
    patch: Parameters<typeof updateTrackMetadata>[2],
  ) => {
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(async () => {
      try {
        const updated = await updateTrackMetadata(sid, trackId, patch);
        replaceTrackInSession(updated);
      } catch (err) {
        setErrorBanner((err as Error).message);
      }
    }, 320);
  };

  const handleTitleChange = (value: string) => {
    if (!session || !currentTrack) return;
    const syncedAlbum = currentTrack.album_auto_synced ? value : currentTrack.album;
    replaceTrackInSession({
      ...currentTrack,
      title: value,
      album: syncedAlbum,
      metadata_provenance: { ...currentTrack.metadata_provenance, title: "manual" },
    });
    scheduleMetadataPatch(session.session_id, currentTrack.id, { title: value });
  };

  const handleArtistsTextChange = (value: string) => {
    if (!session || !currentTrack) return;
    const list = value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    replaceTrackInSession({
      ...currentTrack,
      artists: list,
      artists_display: value,
      metadata_provenance: { ...currentTrack.metadata_provenance, artists: "manual" },
    });
    scheduleMetadataPatch(session.session_id, currentTrack.id, { artists_text: value });
  };

  const handleAlbumChange = (value: string) => {
    if (!session || !currentTrack) return;
    const autoSynced = !value.trim();
    replaceTrackInSession({
      ...currentTrack,
      album: value,
      album_auto_synced: autoSynced,
      metadata_provenance: {
        ...currentTrack.metadata_provenance,
        album: autoSynced ? "auto_from_title" : "manual",
      },
    });
    scheduleMetadataPatch(session.session_id, currentTrack.id, { album: value });
  };

  const handleSelectArtwork = async (artworkId: string) => {
    if (!session || !currentTrack) return;
    const chosen = currentTrack.artwork_candidates.find((a) => a.id === artworkId);
    if (chosen) {
      replaceTrackInSession({
        ...currentTrack,
        selected_artwork_id: artworkId,
        selected_artwork_url: chosen.url,
        artwork_candidates: currentTrack.artwork_candidates.map((a) => ({
          ...a,
          selected: a.id === artworkId,
        })),
      });
    }
    try {
      const updated = await updateTrackMetadata(session.session_id, currentTrack.id, {
        selected_artwork_id: artworkId,
      });
      replaceTrackInSession(updated);
    } catch (err) {
      setErrorBanner((err as Error).message);
    }
  };

  const handleApplyCandidate = async (
    source: string,
    fields?: ("title" | "artists" | "album")[],
  ) => {
    if (!session || !currentTrack) return;
    try {
      const updated = await applyMetadataCandidate(
        session.session_id,
        currentTrack.id,
        source,
        fields,
      );
      replaceTrackInSession(updated);
    } catch (err) {
      setErrorBanner((err as Error).message);
    }
  };

  const handleRefreshSearch = async () => {
    if (!session || !currentTrack) return;
    setRefreshingSearch(true);
    setErrorBanner(null);
    try {
      const updated = await refreshArtworkSearch(session.session_id, currentTrack.id);
      replaceTrackInSession(updated);
      syncHealth();
    } catch (err) {
      setErrorBanner((err as Error).message);
    } finally {
      setRefreshingSearch(false);
    }
  };

  const handleUploadArtwork = async (file: File) => {
    if (!session || !currentTrack) return;
    setUploadingArt(true);
    setErrorBanner(null);
    try {
      const updated = await uploadCustomArtwork(session.session_id, currentTrack.id, file);
      replaceTrackInSession(updated);
    } catch (err) {
      setErrorBanner((err as Error).message);
    } finally {
      setUploadingArt(false);
    }
  };

  const handleTagsChange = async (tagIds: string[]) => {
    if (!session || !currentTrack) return;
    replaceTrackInSession({ ...currentTrack, selected_tag_ids: tagIds });
    try {
      const updated = await updateTrackTags(session.session_id, currentTrack.id, tagIds);
      replaceTrackInSession(updated);
    } catch (err) {
      setErrorBanner((err as Error).message);
    }
  };

  const handleCreateCustomTag = async (category: "language" | "mood", name: string) => {
    try {
      const res = await createCustomTag(category, name);
      setCatalog(res.catalog);
      return res.tag;
    } catch (err) {
      setErrorBanner((err as Error).message);
      return null;
    }
  };

  const handleToggleQueue = async () => {
    if (!session || !currentTrack) return;
    try {
      const nextSession = currentTrack.in_queue
        ? await removeFromQueue(session.session_id, currentTrack.id)
        : await restoreToQueue(session.session_id, currentTrack.id);
      setSession(nextSession);
    } catch (err) {
      setErrorBanner((err as Error).message);
    }
  };

  const attachJobStream = (job: DownloadJobResponse, autoTriggerFile: boolean) => {
    setActiveJob(job);
    sseCleanupRef.current?.();
    sseCleanupRef.current = subscribeToJobEvents(
      job.job_id,
      async (update) => {
        setActiveJob(update);
        if (["completed", "failed", "cancelled"].includes(update.status)) {
          try {
            const refreshed = await getSession(update.session_id);
            setSession(refreshed);
          } catch {
            // ignore refresh failure
          }
          if (autoTriggerFile && update.status === "completed" && update.files.length === 1) {
            const a = document.createElement("a");
            a.href = resolveApiUrl(update.files[0].download_url);
            a.download = update.files[0].file_name;
            document.body.appendChild(a);
            a.click();
            a.remove();
          }
        }
      },
      () => {},
    );
  };

  const handleDownloadSingle = async () => {
    if (!session || !currentTrack) return;
    setErrorBanner(null);
    try {
      const job = await startSingleDownload(session.session_id, currentTrack.id);
      attachJobStream(job, true);
    } catch (err) {
      setErrorBanner((err as Error).message);
    }
  };

  const handleDownloadPlaylist = async () => {
    if (!session) return;
    setErrorBanner(null);
    try {
      const job = await startPlaylistDownload(session.session_id);
      attachJobStream(job, false);
    } catch (err) {
      setErrorBanner((err as Error).message);
    }
  };

  const handleCancelJob = async () => {
    if (!activeJob) return;
    try {
      const updated = await cancelDownloadJob(activeJob.job_id);
      setActiveJob(updated);
    } catch (err) {
      setErrorBanner((err as Error).message);
    }
  };

  const isBusyDownloading =
    activeJob?.status === "queued" || activeJob?.status === "running";

  return (
    <div className="mx-auto flex min-h-screen max-w-[1440px] flex-col gap-5 px-4 py-5 sm:px-8 sm:py-7">
      <HeaderBar
        url={url}
        onUrlChange={setUrl}
        onAnalyze={handleAnalyze}
        analyzing={analyzing}
        queueCount={session?.queue_track_ids.length ?? 0}
        ffmpegAvailable={ffmpegAvailable}
      />

      {errorBanner && (
        <div
          role="alert"
          className="flex items-center gap-2.5 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="size-4 shrink-0" />
          <span className="flex-1">{errorBanner}</span>
          <button
            type="button"
            onClick={() => setErrorBanner(null)}
            className="cursor-pointer text-xs underline opacity-80 hover:opacity-100"
          >
            Cerrar
          </button>
        </div>
      )}

      {session?.notice && (
        <div className="flex items-center gap-2.5 rounded-2xl border border-lang/30 bg-lang/10 px-4 py-3 text-xs text-lang">
          <Info className="size-4 shrink-0" />
          <span>{session.notice}</span>
        </div>
      )}

      {!session || !currentTrack ? (
        <EmptyState onFillExampleUrl={(example) => setUrl(example)} />
      ) : (
        <>
          <TrackNavBar
            tracks={session.tracks}
            currentIndex={currentIndex}
            processedCount={session.processed_tracks}
            onSelectIndex={handleSelectIndex}
          />

          <main
            className={`relative grid gap-5 transition-opacity md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.15fr)] ${
              loadingTrackId === currentTrack.id ? "opacity-65" : "opacity-100"
            }`}
          >
            {loadingTrackId === currentTrack.id && (
              <div className="pointer-events-none absolute top-3 right-3 z-20 inline-flex items-center gap-2 rounded-full border border-border bg-card/90 px-3 py-1 text-xs text-primary shadow">
                <Loader2 className="size-3.5 animate-spin" />
                <span>Cargando metadatos y carátulas...</span>
              </div>
            )}

            <PlayerColumn
              track={currentTrack}
              hasPrev={currentIndex > 0}
              hasNext={currentIndex < session.tracks.length - 1}
              onPrevTrack={() => handleSelectIndex(currentIndex - 1)}
              onNextTrack={() => handleSelectIndex(currentIndex + 1)}
              onSelectArtwork={handleSelectArtwork}
            />

            <MetadataEditorColumn
              track={currentTrack}
              catalog={catalog}
              onTitleChange={handleTitleChange}
              onArtistsTextChange={handleArtistsTextChange}
              onAlbumChange={handleAlbumChange}
              onApplyCandidate={handleApplyCandidate}
              onTagsChange={handleTagsChange}
              onCreateCustomTag={handleCreateCustomTag}
            />

            <SourcesArtworkColumn
              track={currentTrack}
              onApplyCandidate={handleApplyCandidate}
              onSelectArtwork={handleSelectArtwork}
              onUploadArtwork={handleUploadArtwork}
              onRefreshSearch={handleRefreshSearch}
              refreshing={refreshingSearch}
              uploading={uploadingArt}
              spotifyNotice={spotifyNotice}
            />
          </main>

          <DownloadProgressDrawer
            job={activeJob}
            onCancel={handleCancelJob}
            onDismiss={() => setActiveJob(null)}
          />

          <ActionFooter
            track={currentTrack}
            queueCount={session.queue_track_ids.length}
            isBusyDownloading={Boolean(isBusyDownloading)}
            onToggleQueue={handleToggleQueue}
            onRetryTrack={() =>
              void ensureTrackProcessed(session.session_id, currentTrack, true)
            }
            onDownloadSingle={handleDownloadSingle}
            onDownloadPlaylist={handleDownloadPlaylist}
          />
        </>
      )}
    </div>
  );
}

export default App;
