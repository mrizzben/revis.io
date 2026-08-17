import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ProjectView from '../src/pages/ProjectView';
import FileViewer from '../src/components/file/FileViewer';
import type { ProjectDetail, DesignFile } from '../src/types';

const project: ProjectDetail = {
  id: 1,
  name: 'Riverside Residence',
  description: 'A house',
  owner_id: 10,
  firm_id: null,
  is_archived: false,
  file_count: 1,
  milestone_count: 1,
  completed_milestone_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  milestones: [
    {
      id: 5,
      project_id: 1,
      name: 'Concept',
      description: null,
      position: 0,
      is_completed: false,
      completed_at: null,
      file_count: 0,
      created_at: '2026-01-01T00:00:00Z',
    },
  ],
  files: [],
};

const file = {
  id: 'f1',
  project_id: 1,
  filename: 'plan.pdf',
  file_type: 'pdf',
  file_size: 1024,
  created_at: '2026-01-01T00:00:00Z',
  milestone_id: 5,
  version_count: 2,
  comment_count: 0,
  current_version: {
    id: 9,
    version_number: 2,
    visibility: 'client_issued',
    is_current: true,
    created_at: '2026-01-01T00:00:00Z',
  },
} as unknown as DesignFile;

function makeUser(role: 'client' | 'architect') {
  return {
    id: 3,
    email: 'u@x.com',
    name: 'U',
    role,
    firm_id: null,
    is_firm_admin: false,
    is_verified: true,
    client_project_id: role === 'client' ? 1 : null,
    created_at: '2026-01-01T00:00:00Z',
  };
}

let user = makeUser('client');

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useParams: () => ({ projectId: '1' }) };
});

vi.mock('../src/hooks/useWebSocket', () => ({
  default: () => ({ isConnected: false, isPolling: true, lastEvent: null }),
}));

vi.mock('../src/stores/authStore', () => ({
  default: (sel?: (s: unknown) => unknown) => (sel ? sel({ user, accessToken: 't' }) : { user }),
}));

vi.mock('../src/api/endpoints/projects', () => ({
  getProject: vi.fn().mockResolvedValue({
    id: 1,
    name: 'Riverside Residence',
    description: 'A house',
    owner_id: 10,
    firm_id: null,
    is_archived: false,
    file_count: 1,
    milestone_count: 1,
    completed_milestone_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    milestones: [
      {
        id: 5,
        project_id: 1,
        name: 'Concept',
        description: null,
        position: 0,
        is_completed: false,
        completed_at: null,
        file_count: 0,
        created_at: '2026-01-01T00:00:00Z',
      },
    ],
    files: [],
  }),
}));
vi.mock('../src/api/endpoints/files', () => ({
  listProjectFiles: vi.fn().mockResolvedValue([]),
  getPreviewUrl: vi.fn().mockResolvedValue('http://preview'),
  getDownloadUrl: vi.fn().mockResolvedValue({ url: 'http://dl' }),
  listVersions: vi.fn().mockResolvedValue([]),
}));
vi.mock('../src/api/endpoints/milestones', () => ({
  listMilestones: vi.fn().mockResolvedValue([
    {
      id: 5,
      project_id: 1,
      name: 'Concept',
      description: null,
      position: 0,
      is_completed: false,
      completed_at: null,
      file_count: 0,
      created_at: '2026-01-01T00:00:00Z',
    },
  ]),
}));
vi.mock('../src/api/endpoints/collaborators', () => ({
  listCollaborators: vi.fn().mockRejectedValue({ response: { status: 404 } }),
}));

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('client role gating', () => {
  beforeEach(() => {
    user = makeUser('client');
  });

  it('client sees only the timeline/board on the project page', async () => {
    renderWithClient(<ProjectView />);
    await waitFor(() => expect(screen.getByText('Riverside Residence')).toBeTruthy());
    // Timeline / board section present
    expect(screen.getByText('Project Timeline')).toBeTruthy();
    expect(screen.getByRole('button', { name: /timeline/i })).toBeTruthy();
    // Nothing else: no stats bar, no all-files panel, no internal workspace
    expect(screen.queryByText('Files')).toBeNull();
    expect(screen.queryByText('Milestones')).toBeNull();
    expect(screen.queryByText('Project Info')).toBeNull();
    expect(screen.queryByText('No design files uploaded yet.')).toBeNull();
  });

  it('architect keeps the stats bar and file list', async () => {
    user = makeUser('architect');
    renderWithClient(<ProjectView />);
    await waitFor(() => expect(screen.getByText('Riverside Residence')).toBeTruthy());
    expect(screen.getByText('Files')).toBeTruthy();
    expect(screen.getByText('Project Info')).toBeTruthy();
  });

  it('client file view has no revision option, only comments', async () => {
    renderWithClient(
      <FileViewer
        file={file}
        isOpen={true}
        onClose={() => undefined}
        milestones={project.milestones}
      />,
    );
    await waitFor(() => expect(screen.getByText('plan.pdf')).toBeTruthy());
    expect(screen.queryByText(/Revisions \(/)).toBeNull();
    expect(screen.getByText(/Comments \(/)).toBeTruthy();
  });

  it('architect file view keeps the revision panel', async () => {
    user = makeUser('architect');
    renderWithClient(
      <FileViewer
        file={file}
        isOpen={true}
        onClose={() => undefined}
        milestones={project.milestones}
      />,
    );
    await waitFor(() => expect(screen.getByText('plan.pdf')).toBeTruthy());
    expect(screen.getByText(/Revisions \(/)).toBeTruthy();
  });
});
