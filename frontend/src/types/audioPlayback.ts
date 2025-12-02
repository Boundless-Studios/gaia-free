/**
 * Shared type definitions for audio playback system
 * Mirrors backend Python types in src/core/audio/audio_models.py
 */

export type PlaybackStatus = 'pending' | 'generating' | 'playing' | 'played' | 'completed' | 'failed';

export interface AudioChunk {
  chunk_id: string;
  request_id: string;
  campaign_id: string;
  artifact_id: string;
  url: string;
  sequence_number: number;
  status: PlaybackStatus;
  mime_type: string;
  size_bytes: number;
  duration_sec?: number;
  storage_path: string;
  bucket?: string;
  played_at?: string;
}

export interface PlaybackRequest {
  request_id: string;
  campaign_id: string;
  playback_group: string;
  status: PlaybackStatus;
  requested_at: string;
  started_at?: string;
  completed_at?: string;
  total_chunks?: number;
  text?: string;
}

export interface PlaybackQueueStatus {
  currently_playing?: {
    request_id: string;
    chunk_count: number;
    total_chunks: number;
    text?: string;
    text_preview?: string;
  };
  pending_requests: Array<{
    request_id: string;
    chunk_count: number;
    text?: string;
    text_preview?: string;
  }>;
  total_pending_requests: number;
  total_pending_chunks: number;
  status_message: string;
}

export interface AudioStreamStartedEvent {
  type: 'audio_stream_started';
  campaign_id: string;
  stream_url: string;
  started_at: string;
  position_sec?: number;
  is_late_join?: boolean;
  chunk_ids: string[];
  request_id?: string;
  text?: string;
}

export interface AudioStreamStoppedEvent {
  type: 'audio_stream_stopped';
  campaign_id: string;
}

export interface AudioChunkReadyEvent {
  type: 'audio_chunk_ready';
  campaign_id: string;
  chunk: {
    id: string;
    url: string;
    mime_type: string;
    size_bytes: number;
    duration_sec?: number;
    chunk_number?: number;
    total_chunks?: number;
  };
  sequence_number: number;
  playback_group: string;
  request_id?: string;
}

export interface PlaybackQueueUpdatedEvent {
  type: 'playback_queue_updated';
  campaign_id: string;
  pending_count: number;
  current_request?: {
    request_id: string;
    chunk_count: number;
    played_count: number;
    status: PlaybackStatus;
  };
  pending_requests: Array<{
    request_id: string;
    chunk_count: number;
    status: PlaybackStatus;
  }>;
}

export interface AudioPlayedMessage {
  type: 'audio_played';
  campaign_id: string;
  chunk_ids: string[];
  connection_token?: string;
}
