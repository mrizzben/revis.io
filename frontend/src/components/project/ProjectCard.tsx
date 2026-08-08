import { Link } from 'react-router-dom';
import useAuthStore from '../../stores/authStore';
import Badge from '../ui/Badge';
import type { Project } from '../../types';

interface ProjectCardProps {
  project: Project;
}

export default function ProjectCard({ project }: ProjectCardProps) {
  const { user } = useAuthStore();
  const isArchitect = user?.role === 'architect';

  const progress = project.milestone_count > 0
    ? Math.round((project.completed_milestone_count / project.milestone_count) * 100)
    : 0;

  const linkTo = isArchitect
    ? `/project/${project.id}/manage`
    : `/project/${project.id}`;

  return (
    <Link to={linkTo} className="border border-border bg-white hover:border-primary-300 transition-colors block group">
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-base font-semibold text-gray-900 group-hover:text-primary-600 transition-colors truncate">
            {project.name}
          </h3>
          {project.is_archived && <Badge variant="warning">Archived</Badge>}
        </div>

        {project.description && (
          <p className="text-sm text-gray-500 mb-4 line-clamp-2">{project.description}</p>
        )}

        {project.milestone_count > 0 && (
          <div className="mb-4">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-gray-500">Progress</span>
              <span className="text-xs text-gray-500">{progress}%</span>
            </div>
            <div className="w-full bg-gray-200 h-1.5">
              <div
                className="bg-primary-600 h-1.5 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        <div className="flex items-center gap-4 text-sm text-gray-500">
          <div className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
            <span>{project.file_count} files</span>
          </div>
          <div className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <span>
              {project.completed_milestone_count}/{project.milestone_count} milestones
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}