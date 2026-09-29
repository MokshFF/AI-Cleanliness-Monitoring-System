import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorAlertProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'System Error',
  message,
  onRetry,
}) => {
  return (
    <div className="bg-red-950/40 border border-red-800/80 rounded-xl p-4 text-red-200 flex items-start justify-between shadow-md my-3">
      <div className="flex items-start space-x-3">
        <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
        <div>
          <h4 className="text-sm font-semibold text-red-300">{title}</h4>
          <p className="text-xs text-red-200/80 mt-1 leading-relaxed">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center space-x-1 px-3 py-1.5 bg-red-900/60 hover:bg-red-900 border border-red-700 rounded-lg text-xs font-medium text-red-100 transition flex-shrink-0"
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1" />
          Retry
        </button>
      )}
    </div>
  );
};
