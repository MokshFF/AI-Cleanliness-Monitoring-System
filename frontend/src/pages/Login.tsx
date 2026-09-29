import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, Lock, User, AlertCircle, ArrowRight } from 'lucide-react';

export const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Please provide both username and password.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await login({ username: username.trim(), password });
      navigate(from, { replace: true });
    } catch (err: any) {
      if (err.response) {
        if (err.response.status === 401) {
          setError('Invalid credentials. Check your username and password.');
        } else if (err.response.status === 403) {
          setError('This account is inactive. Contact the system administrator.');
        } else {
          setError(err.response.data?.detail || 'Authentication failed. Please try again.');
        }
      } else if (err.request) {
        setError('Backend server unavailable. Please check that the API service is running on port 8000.');
      } else {
        setError('An unexpected network error occurred.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1120] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background visual elements */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-md bg-[#151F32] border border-[#24324D] rounded-2xl shadow-2xl p-8 relative z-10">
        {/* Header Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex p-3 bg-blue-600/20 border border-blue-500/40 rounded-xl text-blue-400 mb-3">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-lg font-bold text-gray-100 tracking-wide uppercase">
            National Cleanliness Monitoring
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Municipal AI Surveillance & Violation Command
          </p>
        </div>

        {/* Error notification */}
        {error && (
          <div className="mb-6 p-3.5 bg-red-950/60 border border-red-800 rounded-xl text-xs text-red-200 flex items-start space-x-2.5">
            <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <span className="leading-relaxed">{error}</span>
          </div>
        )}

        {/* Login form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
              Username or Email
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                <User className="w-4 h-4" />
              </div>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. admin or operator1"
                required
                className="w-full pl-10 pr-4 py-2.5 bg-[#0E1626] border border-[#24324D] rounded-xl text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
              Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                className="w-full pl-10 pr-4 py-2.5 bg-[#0E1626] border border-[#24324D] rounded-xl text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-medium text-sm rounded-xl shadow-lg shadow-blue-900/30 flex items-center justify-center space-x-2 transition"
          >
            <span>{isSubmitting ? 'Authenticating...' : 'Sign In to Command Center'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        {/* Credentials guide for testing/evaluation */}
        <div className="mt-8 pt-4 border-t border-[#24324D] text-[11px] text-gray-400 bg-[#0E1626]/70 p-3 rounded-lg border">
          <p className="font-semibold text-gray-300 mb-1">Default Bootstrap Credentials:</p>
          <div className="flex justify-between">
            <span>Admin Username:</span>
            <code className="text-blue-400 font-mono">admin</code>
          </div>
          <div className="flex justify-between mt-0.5">
            <span>Admin Password:</span>
            <code className="text-blue-400 font-mono">AdminSecurePassword@2026</code>
          </div>
        </div>
      </div>
    </div>
  );
};
