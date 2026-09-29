import React, { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border-2 border-dashed border-[#24324D] rounded-xl my-4">
      <div className="p-3 bg-[#151F32] rounded-full text-gray-400 mb-3">
        {icon || <Inbox className="w-8 h-8 text-gray-500" />}
      </div>
      <h4 className="text-base font-medium text-gray-200">{title}</h4>
      {description && <p className="text-xs text-gray-400 max-w-sm mt-1 mb-4 leading-relaxed">{description}</p>}
      {action && <div>{action}</div>}
    </div>
  );
};
