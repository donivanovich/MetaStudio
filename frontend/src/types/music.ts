export type TrackStatus =
  | "pending"
  | "processing"
  | "ready"
  | "downloading"
  | "downloaded"
  | "error";

export interface MetadataSourceCandidate {
  source: string;
  title: string;
  artists: string[];
  album: string | null;
  duration_seconds: number | null;
  confidence: number;
  external_id: string | null;
  genres: string[];
  language: string | null;
  preview_url: string | null;
  artwork_url: string | null;
  provenance: Record<string, string>;
}

export interface ArtworkCandidate {
  id: string;
  source: string;
  url: string;
  width: number | null;
  height: number | null;
  format: string;
  is_custom: boolean;
  selected: boolean;
}

export interface TagSuggestion {
  tag_id: string;
  category: "language" | "mood";
  name: string;
  display_name: string;
  confidence: number;
  source: string;
  rationale: string | null;
}

export interface TrackResponse {
  id: string;
  index: number;
  source_id: string;
  source_url: string;
  platform: string;
  audio_downloadable: boolean;
  status: TrackStatus;
  error_message: string | null;

  title: string;
  artists: string[];
  artists_display: string;
  album: string;
  album_auto_synced: boolean;
  selected_artwork_id: string | null;
  selected_artwork_url: string | null;

  duration_seconds: number | null;
  preview_audio_url: string | null;

  metadata_candidates: MetadataSourceCandidate[];
  artwork_candidates: ArtworkCandidate[];
  suggested_tags: TagSuggestion[];
  selected_tag_ids: string[];
  metadata_provenance: Record<string, string>;

  in_queue: boolean;
  download_progress: number;
  downloaded_file_name: string | null;
  download_url: string | null;
}

export interface SessionResponse {
  session_id: string;
  source_url: string;
  platform: string;
  is_playlist: boolean;
  playlist_title: string | null;
  notice: string | null;
  total_tracks: number;
  processed_tracks: number;
  queue_track_ids: string[];
  tracks: TrackResponse[];
}

export interface TagDefinition {
  id: string;
  category: "language" | "mood";
  name: string;
  display_name: string;
  aliases: string[];
  custom: boolean;
}

export interface TagCatalogResponse {
  catalog_version: string;
  languages: TagDefinition[];
  moods: TagDefinition[];
}

export interface DownloadJobResponse {
  job_id: string;
  session_id: string;
  job_type: "single" | "playlist";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  total_tracks: number;
  completed_tracks: number;
  failed_tracks: number;
  pending_tracks: number;
  current_track_id: string | null;
  current_track_title: string | null;
  current_track_progress: number;
  zip_ready: boolean;
  zip_download_url: string | null;
  files: Array<{ track_id: string; file_name: string; download_url: string }>;
  errors: Array<{ track_id: string; title: string; error: string }>;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  ffmpeg: {
    available: boolean;
    source: string | null;
    version: string | null;
    error: string | null;
  };
  yt_dlp_version: string;
  providers: Record<string, boolean>;
}
