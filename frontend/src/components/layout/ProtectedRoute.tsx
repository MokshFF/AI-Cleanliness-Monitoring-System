import React, { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { UserRole } from '../../types/auth';
import { ShieldAlert } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0B1120]">
        <LoadingSpinner message="Validating Command Session..." size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center h-full">
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-full text-red-400 mb-4">
          <ShieldAlert className="w-12 h-12" />
        </div>
        <h2 className="text-xl font-bold text-gray-100">Access Restricted</h2>
        <p className="text-sm text-gray-400 max-w-md mt-2 leading-relaxed">
          You do not possess the required administrator privileges to view this management module.
          Your role is currently registered as <strong className="text-blue-400">{user.role}</strong>.
        </p>
      </div>
    );
  }

  return <>{children}</>;
};
