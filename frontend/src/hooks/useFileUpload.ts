import { useState, useCallback } from 'react';
import * as filesApi from '../api/endpoints/files';

const MULTIPART_THRESHOLD = 100 * 1024 * 1024; // 100MB

interface UploadState {
  isUploading: boolean;
  progress: number;
  error: string | null;
  fileId: string | null;
}

export function useFileUpload() {
  const [state, setState] = useState<UploadState>({
    isUploading: false,
    progress: 0,
    error: null,
    fileId: null,
  });

  const upload = useCallback(
    async (
      projectId: number,
      file: File,
      milestoneId?: number,
      onProgress?: (pct: number) => void,
    ): Promise<string | null> => {
      setState({ isUploading: true, progress: 0, error: null, fileId: null });

      try {
        const isMultipart = file.size > MULTIPART_THRESHOLD;

        if (!isMultipart) {
          // Single PUT upload
          const { url, file_id } = await filesApi.getUploadUrl({
            project_id: projectId,
            milestone_id: milestoneId || null,
            filename: file.name,
            content_type: file.type || 'application/octet-stream',
            file_size: file.size,
          });

          // XHR for progress tracking
          await new Promise<void>((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('PUT', url);
            xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');

            xhr.upload.onprogress = (event) => {
              if (event.lengthComputable) {
                const pct = Math.round((event.loaded / event.total) * 100);
                setState((prev) => ({ ...prev, progress: pct }));
                onProgress?.(pct);
              }
            };

            xhr.onload = () => {
              if (xhr.status >= 200 && xhr.status < 300) resolve();
              else reject(new Error(`Upload failed with status ${xhr.status}`));
            };

            xhr.onerror = () => reject(new Error('Network error during upload'));

            xhr.send(file);
          });

          // Notify completion
          await filesApi.uploadComplete(file_id);
          setState((prev) => ({ ...prev, isUploading: false, progress: 100, fileId: file_id }));
          return file_id;
        } else {
          // Multipart upload
          const partSize = 25 * 1024 * 1024; // 25MB
          const { upload_id, key, file_id } = await filesApi.initiateMultipart({
            project_id: projectId,
            milestone_id: milestoneId || null,
            filename: file.name,
            content_type: file.type || 'application/octet-stream',
            file_size: file.size,
            part_size: partSize,
          });

          const partCount = Math.ceil(file.size / partSize);
          const parts: Array<{ PartNumber: number; ETag: string }> = [];

          // Upload parts in batches of 5
          for (let i = 0; i < partCount; i += 5) {
            const batch = Array.from(
              { length: Math.min(5, partCount - i) },
              (_, j) => i + j + 1,
            );

            const { urls } = await filesApi.getPartUrls(upload_id, {
              key,
              part_numbers: batch,
            });

            const batchResults = await Promise.all(
              batch.map(async (partNum) => {
                const start = (partNum - 1) * partSize;
                const end = Math.min(start + partSize, file.size);
                const chunk = file.slice(start, end);

                const result = await new Promise<{ ETag: string }>((resolve, reject) => {
                  const xhr = new XMLHttpRequest();
                  xhr.open('PUT', urls[partNum]);

                  xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                      const etag = xhr.getResponseHeader('ETag') || '';
                      resolve({ ETag: etag.replace(/"/g, '') });
                    } else {
                      reject(new Error(`Part ${partNum} failed: ${xhr.status}`));
                    }
                  };

                  xhr.onerror = () => reject(new Error(`Network error on part ${partNum}`));

                  xhr.upload.onprogress = (event) => {
                    if (event.lengthComputable) {
                      const partProgress = event.loaded / event.total;
                      const overall = Math.round(
                        ((partNum - 1 + partProgress) / partCount) * 100,
                      );
                      setState((prev) => ({ ...prev, progress: overall }));
                      onProgress?.(overall);
                    }
                  };

                  xhr.send(chunk);
                });

                return { PartNumber: partNum, ETag: result.ETag };
              }),
            );

            parts.push(...batchResults);
          }

          await filesApi.completeMultipart(upload_id, { key, parts });
          setState((prev) => ({ ...prev, isUploading: false, progress: 100, fileId: file_id }));
          return file_id;
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Upload failed';
        setState((prev) => ({
          ...prev,
          isUploading: false,
          error: message,
        }));
        return null;
      }
    },
    [],
  );

  const reset = useCallback(() => {
    setState({ isUploading: false, progress: 0, error: null, fileId: null });
  }, []);

  return {
    ...state,
    upload,
    reset,
  };
}
