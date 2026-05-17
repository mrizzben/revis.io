import { Navigate, useLocation } from 'react-router-dom';
import useAuthStore from '../../stores/authStore';

interface ProtectedRouteProps {
  children?: React.ReactNode;
  requiredRole?: 'architect' | 'client';
}

export default function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user?.role !== requiredRole) {
    return <Navigate to="/dashboard" replace />;
  }

  return children ?? <></>;
}