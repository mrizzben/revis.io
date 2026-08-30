// ── Auth ──────────────────────────────────────────────────
export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  role: 'architect' | 'client' | 'admin';
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
  role: 'admin' | 'architect' | 'client';
  firm_id: number | null;
  is_firm_admin: boolean;
  is_verified: boolean;
  client_project_id: number | null;
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

export type RevisionVisibility =
  | 'internal'
  | 'review'
  | 'client_issued'
  | 'superseded'
  | 'archived';

export type ScanStatus = 'pending' | 'clean' | 'infected' | 'error' | 'skipped';

export interface UserBrief {
  id: number;
  email?: string;
  name: string;
}

export interface FileVersion {
  id: number;
  file_id: string;
  version_number: number;
  file_size: number;
  content_hash: string | null;
  revision_message: string | null;
  name: string | null;
  description: string | null;
  visibility: RevisionVisibility;
  scan_status: ScanStatus;
  mime_valid: boolean;
  restored_from_superseded: boolean;
  milestone_id: number | null;
  milestone_name: string | null;
  issued_at: string | null;
  superseded_at: string | null;
  uploaded_by: UserBrief | null;
  issued_by: UserBrief | null;
  is_current: boolean;
  download_url?: string | null;
  created_at: string;
}

export interface DesignFile {
  id: string;
  project_id: number;
  milestone_id: number | null;
  design_option_id: number | null;
  design_option_name: string | null;
  parent_file_id: string | null;
  filename: string;
  file_type: string;
  content_type: string;
  file_size: number;
  thumbnail_status: ThumbnailStatus;
  preview_status: string | null;
  is_deleted: boolean;
  version_number: number;
  version_count: number;
  current_version: FileVersion | null;
  versions?: FileVersion[];
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
  // Upload a new revision of an existing design item (T1).
  file_id?: string;
  revision_message?: string;
  name?: string;
  description?: string;
  design_option_id?: number;
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
  file_id?: string;
  revision_message?: string;
  name?: string;
  description?: string;
  design_option_id?: number;
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

// ── Reviews (T3) ───────────────────────────────────────────
export type ReviewStatus = 'draft' | 'in_review' | 'changes_requested' | 'approved';

export interface Review {
  id: number;
  project_id: number;
  file_id: string;
  revision_id: number | null;
  revision_number: number | null;
  status: ReviewStatus;
  is_client_review: boolean;
  decision_comment: string | null;
  requested_by: UserBrief | null;
  reviewer: UserBrief | null;
  decided_by: UserBrief | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateReviewRequest {
  reviewer_id: number;
  revision_id?: number | null;
  is_client_review?: boolean;
  note?: string;
}

export interface ReviewTransitionRequest {
  action: 'start' | 'approve' | 'request_changes';
  comment?: string;
}

// ── Activity (T6) ──────────────────────────────────────────
export interface ActivityEvent {
  id: number;
  project_id: number;
  event_type: string;
  entity_type: string;
  entity_id: string | null;
  payload: Record<string, unknown>;
  actor: UserBrief | null;
  created_at: string;
}

// ── Design Options (T5) ────────────────────────────────────
export interface DesignOption {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  is_current: boolean;
  is_archived: boolean;
  file_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateDesignOptionRequest {
  name: string;
  description?: string;
}

export interface UpdateDesignOptionRequest {
  name?: string;
  description?: string;
  is_current?: boolean;
  is_archived?: boolean;
}

export interface ForkItemRequest {
  file_id: string;
}

// ── Comparison (T4) ────────────────────────────────────────
export type DiffRegionKind = 'added' | 'removed' | 'modified';

export interface DiffRegion {
  x: number;
  y: number;
  w: number;
  h: number;
  kind: DiffRegionKind;
}

export interface DiffPage {
  page_number: number;
  width: number;
  height: number;
  diff_ratio: number;
  changed: boolean;
  regions: DiffRegion[];
  from_url: string | null;
  to_url: string | null;
  overlay_url: string | null;
}

export interface RevisionDiff {
  status: 'ready' | 'pending' | 'unavailable';
  poll_url: string | null;
  page_count: number;
  pages: DiffPage[];
}

export interface ComparisonResult {
  file_id: string;
  file_type: string;
  supported: boolean;
  explanation: string | null;
  from: FileVersion;
  to: FileVersion;
  diff: RevisionDiff | null;
}

// ── Internal Collaboration ────────────────────────────────
export interface CollaboratorBrief {
  user_id: number;
  email: string;
  name: string;
}

export interface CollaboratorMember extends CollaboratorBrief {
  role: string;
  joined_at: string;
}

export interface CollaboratorsResponse {
  collaborators: CollaboratorMember[];
  owner: CollaboratorBrief | null;
}

export interface Mention {
  user_id: number;
  name: string;
}

export interface InternalNoteReply {
  id: number;
  author: { id: number; name: string } | null;
  body: string;
  parent_id: number;
  created_at: string;
}

export interface InternalNote {
  id: number;
  author: { id: number; name: string } | null;
  body: string;
  mentions: Mention[];
  replies: InternalNoteReply[];
  created_at: string;
  updated_at: string;
}

export interface InternalNotesResponse {
  notes: InternalNote[];
}

export interface ToDo {
  id: number;
  title: string;
  description: string | null;
  status: 'open' | 'complete';
  assignee: { id: number; name: string } | null;
  created_by: { id: number; name: string } | null;
  created_at: string;
  updated_at: string;
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
  | 'revision_created'
  | 'revision_restored'
  | 'revision_issued'
  | 'review_requested'
  | 'review_updated'
  | 'milestone_updated'
  | 'comment_added'
  | 'internal_note_added'
  | 'todo_added'
  | 'todo_updated'
  | 'todo_deleted'
  | 'ping'
  | 'pong';

export interface WsEvent {
  type: WsEventType;
  file_id?: string;
  filename?: string;
  milestone_id?: number;
  is_completed?: boolean;
  comment_id?: number;
  note_id?: number;
  parent_id?: number;
  todo_id?: number;
}

// ── Client Access (secure link, no sign-up) ────────────────
export interface ClientAccessInfo {
  project_name: string;
  archived: boolean;
}

export interface ClientAccessAuth {
  token: string;
  password: string;
}

export interface ClientAccessAuthResponse {
  access_token: string;
  token_type: string;
  project_id: number;
  project_name: string;
  expires_in: number;
}

export interface ClientAccessSetupResponse {
  token: string;
  url: string;
  password_set: boolean;
}

export type NotificationType =
  | 'file_uploaded'
  | 'milestone_completed'
  | 'comment_replied'
  | 'invitation_received'
  | 'mention'
  | 'todo_assigned';

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
  detail:
    | string
    | Array<{
        loc: (string | number)[];
        msg: string;
        type: string;
      }>;
}
