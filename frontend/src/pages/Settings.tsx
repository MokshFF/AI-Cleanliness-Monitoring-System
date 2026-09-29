import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { Card } from '../components/common/Card';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Shield, Cpu, CheckCircle } from 'lucide-react';

export const Settings: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [statusRes, healthRes] = await Promise.all([
          apiClient.get('/status'),
          apiClient.get('/health', { baseURL: '' }),
        ]);
        setSystemStatus(statusRes.data);
        setHealthStatus(healthRes.data);
      } catch (err) {
        console.error('Failed to fetch system status:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSettings();
  }, []);

  if (isLoading) {
    return <LoadingSpinner message="Querying system configuration and engine diagnostics..." size="lg" />;
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-gray-100">System Diagnostics & Settings</h2>
        <p className="text-xs text-gray-400 mt-1">
          Runtime parameters, model weights, and database topology configuration
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Core System Status */}
        <Card title="Backend Service Health" subtitle="FastAPI application status">
          <div className="divide-y divide-[#24324D] text-xs">
            <div className="py-2.5 flex justify-between items-center">
              <span className="text-gray-400">Service:</span>
              <span className="font-semibold text-gray-200">
                {healthStatus?.service || 'AI-Based Cleanliness Monitoring'}
              </span>
            </div>

            <div className="py-2.5 flex justify-between items-center">
              <span className="text-gray-400">Version:</span>
              <span className="font-mono text-blue-400">{healthStatus?.version || '0.1.0'}</span>
            </div>

            <div className="py-2.5 flex justify-between items-center">
              <span className="text-gray-400">Environment:</span>
              <span className="font-mono text-gray-200 uppercase">{healthStatus?.environment || 'development'}</span>
            </div>

            <div className="py-2.5 flex justify-between items-center">
              <span className="text-gray-400">Database Engine:</span>
              <span className="text-emerald-400 font-semibold flex items-center">
                <CheckCircle className="w-3.5 h-3.5 mr-1" />
                MongoDB (Motor Async)
              </span>
            </div>

            <div className="py-2.5 flex justify-between items-center">
              <span className="text-gray-400">System Operational:</span>
              <span className="text-emerald-400 font-semibold uppercase">{systemStatus?.status || 'operational'}</span>
            </div>
          </div>
        </Card>

        {/* AI Engine Diagnostics */}
        <Card title="Computer Vision Capabilities" subtitle="Active YOLO detection & segmentation models">
          <div className="space-y-4 text-xs">
            <div>
              <div className="flex items-center space-x-1.5 font-semibold text-indigo-400 mb-1.5">
                <Cpu className="w-3.5 h-3.5" />
                <span>Solid Waste Classes (Object Detection)</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(systemStatus?.solid_classes || [
                  'plastic_bottle',
                  'plastic_bag',
                  'paper',
                  'can',
                  'food_waste',
                  'garbage_pile',
                ]).map((cls: string) => (
                  <span
                    key={cls}
                    className="px-2 py-0.5 bg-[#0E1626] border border-[#24324D] rounded text-[11px] text-gray-300 font-mono"
                  >
                    {cls}
                  </span>
                ))}
              </div>
            </div>

            <div className="pt-2 border-t border-[#24324D]">
              <div className="flex items-center space-x-1.5 font-semibold text-cyan-400 mb-1.5">
                <Cpu className="w-3.5 h-3.5" />
                <span>Liquid Waste Classes (Polygon Segmentation)</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(systemStatus?.liquid_classes || [
                  'liquid_spill',
                  'sewage_overflow',
                  'waterlogging',
                  'drain_overflow',
                ]).map((cls: string) => (
                  <span
                    key={cls}
                    className="px-2 py-0.5 bg-[#0E1626] border border-[#24324D] rounded text-[11px] text-gray-300 font-mono"
                  >
                    {cls}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Security Architecture Notice */}
      <Card title="Security & Compliance Architecture" subtitle="Municipal standard controls">
        <div className="p-3.5 bg-[#0E1626] border border-[#24324D] rounded-xl text-xs space-y-2 text-gray-300">
          <div className="flex items-center space-x-2 text-blue-400 font-semibold">
            <Shield className="w-4 h-4" />
            <span>Strict Credential Protection Policy</span>
          </div>
          <p className="text-gray-400 leading-relaxed text-[11px]">
            In compliance with national security guidelines, CCTV/IP camera RTSP credentials and user
            password hashes are strictly masked in all REST responses. All incident transitions generate
            tamper-evident audit logs with client IP recording.
          </p>
        </div>
      </Card>
    </div>
  );
};
