interface ProgressBarProps {
  value: number;
  label?: string;
  showPercentage?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

const heightStyles = { sm: 'h-1.5', md: 'h-2.5' };

export default function ProgressBar({
  value,
  label,
  showPercentage = false,
  size = 'md',
  className = '',
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercentage) && (
        <div className="flex justify-between mb-1">
          {label && <span className="text-xs text-gray-600">{label}</span>}
          {showPercentage && <span className="text-xs text-gray-500">{Math.round(clamped)}%</span>}
        </div>
      )}
      <div className={`w-full bg-gray-200 ${heightStyles[size]}`}>
        <div
          className={`bg-primary-600 transition-all duration-300 ${heightStyles[size]}`}
          style={{ width: `${clamped}%` }}
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}