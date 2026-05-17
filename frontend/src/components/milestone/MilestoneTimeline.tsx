import { useState, useCallback } from 'react';
import type { Milestone } from '../../types';
import { updateMilestone } from '../../api/endpoints/milestones';
import { useQueryClient } from '@tanstack/react-query';
import MilestoneCard from './MilestoneCard';
import ProgressBar from '../ui/ProgressBar';

interface MilestoneTimelineProps {
  milestones: Milestone[];
  isArchitect?: boolean;
  projectId?: number;
  onEdit?: (milestone: Milestone) => void;
  onDelete?: (id: number) => void;
}

export default function MilestoneTimeline({
  milestones,
  isArchitect = false,
  projectId,
  onEdit,
  onDelete,
}: MilestoneTimelineProps) {
  const queryClient = useQueryClient();
  const [animatingId, setAnimatingId] = useState<number | null>(null);

  const sorted = [...milestones].sort((a, b) => a.position - b.position);

  const firstIncompleteIndex = sorted.findIndex((m) => !m.is_completed);
  const currentIndex = firstIncompleteIndex === -1 ? -1 : firstIncompleteIndex;

  const completedCount = sorted.filter((m) => m.is_completed).length;
  const percent = sorted.length > 0 ? (completedCount / sorted.length) * 100 : 0;

  const handleToggle = useCallback(
    async (id: number, completed: boolean) => {
      setAnimatingId(id);
      await updateMilestone(id, { is_completed: completed });
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: ['project', projectId] });
        queryClient.invalidateQueries({ queryKey: ['milestones', projectId] });
      }
      setTimeout(() => setAnimatingId(null), 600);
    },
    [projectId, queryClient],
  );

  if (sorted.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <svg className="w-12 h-12 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        <p className="text-sm text-gray-500 max-w-xs">
          No milestones defined yet. Create milestones to track project phases.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <ProgressBar
          value={percent}
          label={`${completedCount}/${sorted.length} milestones complete`}
          showPercentage
          className="max-w-md"
        />
      </div>

      {/* Mobile: horizontal cards */}
      <div className="md:hidden space-y-3">
        {sorted.map((milestone, idx) => (
          <div
            key={milestone.id}
            className={`transition-transform duration-300 ${
              animatingId === milestone.id ? 'scale-105' : ''
            }`}
          >
            <MilestoneCard
              milestone={milestone}
              isArchitect={isArchitect}
              isCurrent={idx === currentIndex}
              onToggle={handleToggle}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          </div>
        ))}
      </div>

      {/* Desktop: vertical timeline */}
      <div className="hidden md:block">
        <div className="relative">
          {sorted.map((milestone, idx) => {
            const isCompleted = milestone.is_completed;
            const isCurrent = idx === currentIndex && !isCompleted;

            return (
              <div key={milestone.id} className="relative flex gap-6 pb-8 last:pb-0">
                {/* Timeline line + dot */}
                <div className="flex flex-col items-center shrink-0">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center border-2 shrink-0 transition-all duration-300 ${
                      animatingId === milestone.id ? 'scale-125' : ''
                    } ${
                      isCompleted
                        ? 'bg-green-500 border-green-500'
                        : isCurrent
                          ? 'bg-blue-50 border-blue-500'
                          : 'bg-white border-gray-300'
                    }`}
                  >
                    {isCompleted ? (
                      <svg className={`w-4 h-4 text-white ${animatingId === milestone.id ? 'animate-bounce' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : isCurrent ? (
                      <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
                    ) : (
                      <div className="w-2.5 h-2.5 rounded-full bg-gray-400" />
                    )}
                  </div>
                  {idx < sorted.length - 1 && (
                    <div
                      className={`w-0.5 flex-1 min-h-[24px] ${
                        isCompleted ? 'bg-green-500' : 'bg-gray-200'
                      }`}
                    />
                  )}
                </div>

                {/* Card */}
                <div
                  className={`flex-1 min-w-0 transition-all duration-300 ${
                    animatingId === milestone.id ? 'scale-[1.02] shadow-lg' : ''
                  } ${animatingId === milestone.id && isCompleted ? 'ring-2 ring-green-300 rounded-lg' : ''}`}
                >
                  <MilestoneCard
                    milestone={milestone}
                    isArchitect={isArchitect}
                    isCurrent={isCurrent}
                    onToggle={handleToggle}
                    onEdit={onEdit}
                    onDelete={onDelete}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
