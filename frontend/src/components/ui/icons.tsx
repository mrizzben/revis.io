import type { SVGProps } from 'react';

/**
 * Shared stroke-based icon set (Heroicons style, 24x24 viewBox).
 * Replaces emoji as structural icons across the app.
 */
const PATHS: Record<string, string> = {
  // file_uploaded / default activity
  document:
    'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
  // milestone_completed, comment_resolved, review_approved
  'check-circle': 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  // comment_created / comment_replied
  chat: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
  // invitation_received
  envelope:
    'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  // mention
  'at-symbol':
    'M16 12a4 4 0 11-8 0 4 4 0 018 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4-9c0 1.933-1.567 3.5-3.5 3.5S10 13.933 10 12s1.567-3.5 3.5-3.5S14 10.067 14 12z',
  // todo_assigned
  'clipboard-check':
    'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
  // revision_issued
  upload: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12',
  // revision_restored
  undo: 'M3 10h10a7 7 0 010 14H8m-5-4l4 4m-4-4l4-4',
  // revision_superseded
  forward: 'M13 5l7 7-7 7M5 5l7 7-7 7',
  // revision_archived
  'archive-box':
    'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4',
  // revision_updated
  pencil:
    'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
  // comment_reopened
  refresh:
    'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  // review_requested
  eye: 'M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z',
  // review_changes_requested
  'pencil-edit':
    'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586zM13.5 4.5l2 2',
  // review_in_review
  magnifier: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  // milestone_changed
  'map-pin':
    'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z',
  // file_deleted
  trash:
    'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16',
  // item_forked
  fork: 'M10 14l2-2m0 0l2 2m-2-2v6m-2 0h4m-2-6c.62-.56 1.45-.96 2.35-1.12 1.8-.33 3.42-1.72 3.97-3.45M10 14c-.62-.56-1.45-.96-2.35-1.12C5.85 12.55 4.23 11.16 3.68 9.43m2.5-2.29h3m-3 0V4m0 3.14H6.18M18.32 4.57h-3m3 0V7.7m0-3.13h.64',
  // option_created / option_updated
  puzzle:
    'M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z',
  // 📌 checkpoint pin
  pin: 'M16.5 4L9.3 11.2m0 0a2 2 0 11-2.83 2.83 2 2 0 012.83-2.83zM9.3 11.2l7.2-7.2M16.5 4l3.5 3.5M13 9l2.5 2.5M9.3 11.2l-5.8 5.8a2 2 0 002.83 2.83l5.8-5.8M9.3 14.03V20m4.5-8.5h3.5l3.5 3.5h-3.5l-3.5-3.5z',
};

export type IconName = keyof typeof PATHS;

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
}

export default function Icon({ name, ...props }: IconProps) {
  return (
    <svg
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.75}
      aria-hidden="true"
      {...props}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
