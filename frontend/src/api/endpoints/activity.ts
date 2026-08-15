import apiClient from '../client';
import type {
  Review,
  CreateReviewRequest,
  ReviewTransitionRequest,
  ActivityEvent,
  DesignOption,
  CreateDesignOptionRequest,
  UpdateDesignOptionRequest,
  ForkItemRequest,
  DesignFile,
} from '../../types';

// ── Reviews (T3) ──────────────────────────────────────────

export async function createReview(
  fileId: string,
  data: CreateReviewRequest,
): Promise<Review> {
  const response = await apiClient.post(`/files/${fileId}/reviews`, data);
  return response.data;
}

export async function listReviews(fileId: string): Promise<Review[]> {
  const response = await apiClient.get(`/files/${fileId}/reviews`);
  return response.data;
}

export async function transitionReview(
  reviewId: number,
  data: ReviewTransitionRequest,
): Promise<Review> {
  const response = await apiClient.post(`/reviews/${reviewId}/transition`, data);
  return response.data;
}

// ── Activity (T6) ─────────────────────────────────────────

export async function listActivity(
  projectId: number,
  eventType?: string,
): Promise<ActivityEvent[]> {
  const response = await apiClient.get(`/projects/${projectId}/activity`, {
    params: { event_type: eventType },
  });
  return response.data;
}

// ── Design Options (T5) ───────────────────────────────────

export async function listOptions(projectId: number): Promise<DesignOption[]> {
  const response = await apiClient.get(`/projects/${projectId}/options`);
  return response.data;
}

export async function createOption(
  projectId: number,
  data: CreateDesignOptionRequest,
): Promise<DesignOption> {
  const response = await apiClient.post(`/projects/${projectId}/options`, data);
  return response.data;
}

export async function updateOption(
  optionId: number,
  data: UpdateDesignOptionRequest,
): Promise<DesignOption> {
  const response = await apiClient.patch(`/options/${optionId}`, data);
  return response.data;
}

export async function forkItem(optionId: number, data: ForkItemRequest): Promise<DesignFile> {
  const response = await apiClient.post(`/options/${optionId}/fork`, data);
  return response.data;
}

export async function listOptionFiles(optionId: number): Promise<DesignFile[]> {
  const response = await apiClient.get(`/options/${optionId}/files`);
  return response.data;
}
