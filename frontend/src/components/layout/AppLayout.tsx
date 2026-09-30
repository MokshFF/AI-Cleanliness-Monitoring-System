import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useWebSocket } from '../../websocket/WebSocketProvider';
import { IncidentAlertToast } from '../alerts/IncidentAlertToast';

export const AppLayout: React.FC = () => {
  const { activeAlerts, dismissAlert } = useWebSocket();

  return (
    <div className="flex flex-col min-h-screen bg-[#0B1120] text-gray-100 font-sans">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <Outlet />
        </main>
      </div>
      <IncidentAlertToast alerts={activeAlerts} onDismiss={dismissAlert} />
    </div>
  );
};
