import React from 'react';
import { Card } from '../components/common/Card';
import { MapPin, BarChart3, Clock, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface PlaceholderPageProps {
  module: 'map' | 'analytics';
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ module }) => {
  const isMap = module === 'map';

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-8">
      <Card className="text-center py-16 px-6">
        <div className="inline-flex p-4 bg-blue-600/10 border border-blue-500/20 rounded-2xl text-blue-400 mb-4">
          {isMap ? <MapPin className="w-12 h-12" /> : <BarChart3 className="w-12 h-12" />}
        </div>

        <h2 className="text-xl font-bold text-gray-100">
          {isMap ? 'GIS Interactive Cleanliness Map' : 'Advanced Multi-Camera Analytics'}
        </h2>

        <p className="text-sm text-gray-400 max-w-md mx-auto mt-2 leading-relaxed">
          {isMap
            ? 'Geographic heatmaps, camera placement pins, and zone alert boundaries will be introduced in Phase 9 following Phase 8 WebSocket real-time alerting.'
            : 'Longitudinal cleanliness trend models, zone violation comparisons, and exportable municipal compliance reports will be delivered in Phase 9.'}
        </p>

        <div className="mt-6 inline-flex items-center space-x-2 px-3.5 py-1.5 bg-[#0E1626] border border-[#24324D] rounded-full text-xs text-amber-400">
          <Clock className="w-3.5 h-3.5" />
          <span>Scheduled for Phase 9 Implementation</span>
        </div>

        <div className="mt-8">
          <Link
            to="/dashboard"
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition"
          >
            <span>Return to Dashboard</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </Card>
    </div>
  );
};
