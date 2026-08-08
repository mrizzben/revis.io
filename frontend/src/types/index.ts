// ── Auth ──────────────────────────────────────────────────
export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  role: 'architect' | 'client';
  invitation_token?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

// ── User ──────────────────────────────────────────────────
export interface User {
  id: number;
  email: string;
  name: string;
  role: 'architect' | 'client';
  firm_id: number | null;
  is_firm_admin: boolean;
  is_verified: boolean;
  created_at: string;
}

// ── Firm ──────────────────────────────────────────────────
export interface Firm {
  id: number;
  name: string;
  member_count: number;
  created_at: string;
}

export interface CreateFirmRequest {
  name: string;
}

// ── Project ───────────────────────────────────────────────
export interface Project {
  id: number;
  name: string;
  description: string | null;
  owner_id: number;
  firm_id: number | null;
  is_archived: boolean;
  file_count: number;
  milestone_count: number;
  completed_milestone_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  milestones: Milestone[];
  files: DesignFile[];
}

export interface CreateProjectRequest {
  name: string;
  description?: string;
  firm_id?: number | null;
}

export interface UpdateProjectRequest {
  name?: string;
  description?: string;
  is_archived?: boolean;
}

// ── Invitation ────────────────────────────────────────────
export interface Invitation {
  id: number;
  email: string;
  token: string;
  expires_at: string;
  is_used: boolean;
  created_at: string;
}

export interface InvitationDetail {
  email: string;
  project_name: string;
  invited_by_name: string;
}

export interface InviteClientRequest {
  email: string;
}

// ── File / DesignFile ─────────────────────────────────────
export type ThumbnailStatus = 'pending' | 'processing' | 'complete' | 'failed' | 'unsupported';

export interface DesignFile {
  id: string;
  project_id: number;
  milestone_id: number | null;
  filename: string;
  file_type: string;
  content_type: string;
  file_size: number;
  thumbnail_status: ThumbnailStatus;
  preview_status: string | null;
  is_deleted: boolean;
  version_number: number;
  comment_count: number;
  uploaded_by: User;
  created_at: string;
  updated_at: string;
}

export interface UploadUrlRequest {
  project_id: number;
  milestone_id?: number | null;
  filename: string;
  content_type: string;
  file_size: number;
}

export interface UploadUrlResponse {
  url: string;
  key: string;
  file_id: string;
}

export interface MultipartInitiateRequest {
  project_id: number;
  milestone_id?: number | null;
  filename: string;
  content_type: string;
  file_size: number;
  part_size: number;
}

export interface MultipartInitiateResponse {
  upload_id: string;
  key: string;
  file_id: string;
}

export interface MultipartPartUrlsRequest {
  key: string;
  part_numbers: number[];
}

export interface MultipartPartUrlsResponse {
  urls: Record<string, string>;
}

export interface MultipartCompleteRequest {
  key: string;
  parts: Array<{ PartNumber: number; ETag: string }>;
}

export interface DownloadUrlResponse {
  url: string;
}

export interface ThumbnailParams {
  size?: 'small' | 'medium';
}

export interface UpdateFileMilestoneRequest {
  milestone_id: number | null;
}

// ── Milestone ─────────────────────────────────────────────
export interface Milestone {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  position: number;
  is_completed: boolean;
  completed_at: string | null;
  file_count: number;
  created_at: string;
}

export interface CreateMilestoneRequest {
  name: string;
  description?: string;
  position?: number;
}

export interface UpdateMilestoneRequest {
  name?: string;
  description?: string;
  position?: number;
  is_completed?: boolean;
}

// ── Comment ───────────────────────────────────────────────
export interface Comment {
  id: number;
  file_id: string;
  parent_id: number | null;
  body: string;
  is_resolved: boolean;
  author: User;
  replies: Comment[];
  created_at: string;
  updated_at: string;
}

export interface CreateCommentRequest {
  body: string;
  parent_id?: number | null;
}

export interface UpdateCommentRequest {
  body?: string;
  is_resolved?: boolean;
}

// ── Project Updates (polling) ─────────────────────────────
export interface ProjectUpdatesResponse {
  has_updates: boolean;
  timestamp: string;
}

// ── WebSocket Events ──────────────────────────────────────
export type WsEventType =
  | 'file_uploaded'
  | 'file_deleted'
  | 'file_updated'
  | 'milestone_updated'
  | 'comment_added'
  | 'ping'
  | 'pong';

export interface WsEvent {
  type: WsEventType;
  file_id?: string;
  filename?: string;
  milestone_id?: number;
  is_completed?: boolean;
  comment_id?: number;
}

// ── Notification ──────────────────────────────────────────
export type NotificationType =
  | 'file_uploaded'
  | 'milestone_completed'
  | 'comment_replied'
  | 'invitation_received';

export interface Notification {
  id: number;
  user_id: number;
  type: NotificationType;
  title: string;
  body: string | null;
  is_read: boolean;
  reference_id: number | null;
  created_at: string;
}

// ── API Error ─────────────────────────────────────────────
export interface ApiError {
  detail: string | Array<{
    loc: (string | number)[];
    msg: string;
    type: string;
  }>;
}