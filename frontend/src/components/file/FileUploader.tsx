import { useCallback, useRef, useState } from 'react';
import ProgressBar from '../ui/ProgressBar';
import Badge from '../ui/Badge';

const ALLOWED_EXTENSIONS = [
  '.png',
  '.jpg',
  '.jpeg',
  '.webp',
  '.pdf',
  '.dwg',
  '.dxf',
  '.skp',
  '.rvt',
  '.ifc',
  '.obj',
  '.stl',
];
const MULTIPART_THRESHOLD = 100 * 1024 * 1024; // 100MB

interface Milestone {
  id: number;
  name: string;
}

interface FileUploaderProps {
  projectId: number;
  milestoneId?: number;
  onUploadSuccess: () => void;
  milestones?: Milestone[];
  onMilestoneSelect?: (milestoneId: number | null) => void;
  // Upload a new revision of an existing design item (T1).
  fileId?: string | null;
  revisionMessage?: string;
}

interface UploadTask {
  id: string;
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'complete' | 'error';
  error?: string;
}

export default function FileUploader({
  projectId,
  milestoneId,
  onUploadSuccess,
  milestones,
  onMilestoneSelect,
  fileId,
  revisionMessage,
}: FileUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [milestoneIdValue, setMilestoneIdValue] = useState<number | null>(milestoneId ?? null);

  const validateFile = (file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file type: ${ext}`;
    }
    if (file.size > 1_073_741_824) {
      return `File too large (max 1GB): ${file.name}`;
    }
    return null;
  };

  const uploadFile = async (task: UploadTask) => {
    setUploadTasks((prev) =>
      prev.map((t) => (t.id === task.id ? { ...t, status: 'uploading' as const } : t)),
    );

    try {
      const isMultipart = task.file.size > MULTIPART_THRESHOLD;

      if (!isMultipart) {
        const { getUploadUrl, uploadComplete } = await import('../../api/endpoints/files');
        const { url, file_id, key } = await getUploadUrl({
          project_id: projectId,
          milestone_id: milestoneIdValue || null,
          filename: task.file.name,
          content_type: task.file.type || 'application/octet-stream',
          file_size: task.file.size,
          file_id: fileId || undefined,
          revision_message: revisionMessage || undefined,
        });

        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open('PUT', url);
          xhr.setRequestHeader('Content-Type', task.file.type || 'application/octet-stream');

          xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
              const pct = Math.round((event.loaded / event.total) * 100);
              setUploadTasks((prev) =>
                prev.map((t) => (t.id === task.id ? { ...t, progress: pct } : t)),
              );
            }
          };

          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) resolve();
            else reject(new Error(`Upload failed: ${xhr.status}`));
          };

          xhr.onerror = () => reject(new Error('Network error'));
          xhr.send(task.file);
        });

        await uploadComplete(file_id, key, revisionMessage || undefined);
      } else {
        const { initiateMultipart, getPartUrls, completeMultipart } =
          await import('../../api/endpoints/files');
        const partSize = 25 * 1024 * 1024; // 25MB

        const { upload_id, key, file_id } = await initiateMultipart({
          project_id: projectId,
          milestone_id: milestoneIdValue || null,
          filename: task.file.name,
          content_type: task.file.type || 'application/octet-stream',
          file_size: task.file.size,
          part_size: partSize,
          file_id: fileId || undefined,
          revision_message: revisionMessage || undefined,
        });

        const partCount = Math.ceil(task.file.size / partSize);
        const parts: Array<{ PartNumber: number; ETag: string }> = [];

        for (let i = 0; i < partCount; i += 5) {
          const batch = Array.from({ length: Math.min(5, partCount - i) }, (_, j) => i + j + 1);

          const { urls } = await getPartUrls(upload_id, {
            key,
            part_numbers: batch,
          });

          const batchResults = await Promise.all(
            batch.map(async (partNum) => {
              const start = (partNum - 1) * partSize;
              const end = Math.min(start + partSize, task.file.size);
              const chunk = task.file.slice(start, end);

              const xhrResult = await new Promise<{ ETag: string }>((resolve, reject) => {
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
                xhr.onerror = () => reject(new Error('Network error'));
                xhr.upload.onprogress = (event) => {
                  if (event.lengthComputable) {
                    const partProgress = Math.round((event.loaded / event.total) * 100);
                    const overall = Math.round(
                      ((partNum - 1 + partProgress / 100) / partCount) * 100,
                    );
                    setUploadTasks((prev) =>
                      prev.map((t) => (t.id === task.id ? { ...t, progress: overall } : t)),
                    );
                  }
                };
                xhr.send(chunk);
              });
              return { PartNumber: partNum, ETag: xhrResult.ETag };
            }),
          );
          parts.push(...batchResults);
        }

        await completeMultipart(upload_id, { key, parts });

        // Record the revision (large-file path) with the uploaded key (T1/T8).
        const { uploadComplete } = await import('../../api/endpoints/files');
        await uploadComplete(file_id, key, revisionMessage || undefined);
      }

      setUploadTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: 'complete', progress: 100 } : t)),
      );
      onUploadSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setUploadTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: 'error', error: msg } : t)),
      );
    }
  };

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      const newTasks: UploadTask[] = [];
      for (const file of Array.from(files)) {
        const error = validateFile(file);
        newTasks.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          file,
          progress: 0,
          status: error ? 'error' : 'pending',
          error: error || undefined,
        });
      }
      if (newTasks.length > 0) {
        setUploadTasks((prev) => [...prev, ...newTasks]);
        newTasks.forEach((task) => {
          if (task.status === 'pending') uploadFile(task);
        });
      }
    },
    [projectId, milestoneIdValue],
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  return (
    <div>
      {milestones && milestones.length > 0 && (
        <div className="flex items-center mb-3 space-x-2">
          <label className="text-sm text-gray-600 font-medium">Milestone:</label>
          <select
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-400"
            value={milestoneIdValue ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              const id = val ? Number(val) : null;
              setMilestoneIdValue(id);
              onMilestoneSelect?.(id);
            }}
          >
            <option value="">No milestone</option>
            {milestones.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
          isDragOver
            ? 'border-primary-400 bg-primary-50'
            : 'border-gray-300 hover:border-primary-300'
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <svg
          className="w-10 h-10 text-gray-400 mx-auto mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        <p className="text-gray-600">
          <span className="text-primary-600 font-medium">Click to upload</span> or drag and drop
        </p>
        <p className="text-xs text-gray-400 mt-1">
          PNG, JPG, WebP, PDF, DWG, DXF, SKP, RVT, IFC, OBJ, STL (max 1GB)
        </p>
        <input
          ref={fileInputRef}
          type="file"
          className="sr-only"
          multiple
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>

      {uploadTasks.length > 0 && (
        <div className="mt-4 space-y-3">
          {uploadTasks.map((task) => (
            <div key={task.id} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium">{task.file.name}</span>
                  {task.status === 'complete' && <Badge variant="success">Done</Badge>}
                  {task.status === 'uploading' && <Badge variant="info">Uploading</Badge>}
                  {task.status === 'error' && <Badge variant="danger">Failed</Badge>}
                </div>
                <span className="text-xs text-gray-400">
                  {(task.file.size / (1024 * 1024)).toFixed(1)} MB
                </span>
              </div>
              <ProgressBar value={task.progress} size="sm" showPercentage />
              {task.error && <p className="text-xs text-red-600 mt-1">{task.error}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
