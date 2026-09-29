import React, { ReactNode } from 'react';

interface CardProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ title, subtitle, action, children, className = '' }) => {
  return (
    <div className={`bg-[#151F32] border border-[#24324D] rounded-xl shadow-lg p-5 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between border-b border-[#24324D]/60 pb-3 mb-4">
          <div>
            {title && <h3 className="text-base font-semibold text-gray-100">{title}</h3>}
            {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
};
