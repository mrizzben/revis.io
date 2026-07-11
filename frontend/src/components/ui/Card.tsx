import type { ReactNode, HTMLAttributes } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const paddingStyles = {
  none: 'p-0',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-8',
};

export default function Card({ children, padding = 'md', className = '', ...props }: CardProps) {
  return (
    <div className={`card ${paddingStyles[padding]} ${className}`.trim()} {...props}>
      {children}
    </div>
  );
}