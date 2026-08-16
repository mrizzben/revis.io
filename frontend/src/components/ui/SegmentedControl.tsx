interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
  ariaLabel?: string;
  className?: string;
}

/** Pill-style segmented control for mutually exclusive views (timeline/board, active/archived). */
export default function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  size = 'md',
  ariaLabel,
  className = '',
}: SegmentedControlProps<T>) {
  const isSm = size === 'sm';
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={`inline-flex rounded-lg bg-gray-100 p-0.5 ${className}`}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.value)}
            className={`
              ${isSm ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'}
              font-medium rounded-md cursor-pointer select-none transition-colors duration-150
              focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500
              ${
                selected
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200/60'
              }
            `}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
