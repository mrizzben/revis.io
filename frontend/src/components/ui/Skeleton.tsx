interface SkeletonProps {
  width?: string;
  height?: string;
  className?: string;
  count?: number;
}

export default function Skeleton({
  width,
  height,
  className = '',
  count = 1,
}: SkeletonProps) {
  const style: React.CSSProperties = {};
  if (width) style.width = width;
  if (height) style.height = height;

  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`animate-pulse bg-gray-200 rounded ${className}`}
          style={style}
        />
      ))}
    </>
  );
}
