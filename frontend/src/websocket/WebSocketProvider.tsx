import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  ReactNode,
} from 'react';
import { useAuth } from '../context/AuthContext';
import {
  ActiveAlert,
  ConnectionStatus,
  IncidentCreatedPayload,
  IncidentUpdatedPayload,
  WebSocketAlertEvent,
} from './alerts';
import { Incident } from '../types/incident';

type IncidentCreatedListener = (payload: IncidentCreatedPayload) => void;
type IncidentUpdatedListener = (payload: IncidentUpdatedPayload) => void;

interface WebSocketContextType {
  connectionStatus: ConnectionStatus;
  activeAlerts: ActiveAlert[];
  dismissAlert: (id: string) => void;
  audioEnabled: boolean;
  toggleAudio: () => void;
  subscribeIncidentCreated: (listener: IncidentCreatedListener) => () => void;
  subscribeIncidentUpdated: (listener: IncidentUpdatedListener) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

// Synthesize a clean, pleasant non-intrusive surveillance alert chime using Web Audio API
const playAlertChime = () => {
  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;

    const ctx = new AudioContextClass();
    const now = ctx.currentTime;

    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gainNode = ctx.createGain();

    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, now); // D5
    osc1.frequency.exponentialRampToValueAtTime(880.0, now + 0.12); // A5

    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(880.0, now + 0.08);

    gainNode.gain.setValueAtTime(0.15, now);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

    osc1.connect(gainNode);
    osc2.connect(gainNode);
    gainNode.connect(ctx.destination);

    osc1.start(now);
    osc2.start(now + 0.08);
    osc1.stop(now + 0.35);
    osc2.stop(now + 0.35);
  } catch (err) {
    // Autoplay restrictions or audio unsupported; ignore safely without degrading visual UI
    console.debug('Alert chime autoplay prevented or unsupported:', err);
  }
};

const MAX_RECENT_INCIDENTS = 200;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { token, isAuthenticated, logout } = useAuth();
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('OFFLINE');
  const [activeAlerts, setActiveAlerts] = useState<ActiveAlert[]>([]);
  const [audioEnabled, setAudioEnabled] = useState<boolean>(() => {
    return localStorage.getItem('alert_audio_enabled') !== 'false';
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const recentIncidentIdsRef = useRef<Set<string>>(new Set());

  // Listeners for page-level state synchronization
  const createdListenersRef = useRef<Set<IncidentCreatedListener>>(new Set());
  const updatedListenersRef = useRef<Set<IncidentUpdatedListener>>(new Set());

  const toggleAudio = useCallback(() => {
    setAudioEnabled((prev) => {
      const next = !prev;
      localStorage.setItem('alert_audio_enabled', String(next));
      return next;
    });
  }, []);

  const dismissAlert = useCallback((id: string) => {
    setActiveAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const subscribeIncidentCreated = useCallback((listener: IncidentCreatedListener) => {
    createdListenersRef.current.add(listener);
    return () => {
      createdListenersRef.current.delete(listener);
    };
  }, []);

  const subscribeIncidentUpdated = useCallback((listener: IncidentUpdatedListener) => {
    updatedListenersRef.current.add(listener);
    return () => {
      updatedListenersRef.current.delete(listener);
    };
  }, []);

  // WebSocket Connection Lifecycle
  useEffect(() => {
    if (!isAuthenticated || !token) {
      if (wsRef.current) {
        wsRef.current.close(1000, 'User logged out');
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      setConnectionStatus('OFFLINE');
      return;
    }

    let isDisposed = false;

    const connect = () => {
      if (isDisposed) return;

      // Close existing socket if open
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      setConnectionStatus((prev) => (prev === 'OFFLINE' ? 'RECONNECTING' : prev));

      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Connect via Vite proxy /ws/alerts or root host
        const wsUrl = `${protocol}//${window.location.host}/ws/alerts?token=${encodeURIComponent(token)}`;

        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
          if (isDisposed) return;
          console.info('Surveillance WebSocket connected');
          setConnectionStatus('CONNECTED');
          reconnectAttemptsRef.current = 0; // Reset exponential backoff
        };

        socket.onmessage = (event) => {
          if (isDisposed) return;
          try {
            const data: WebSocketAlertEvent = JSON.parse(event.data);

            if (data.type === 'CONNECTED') {
              console.info('WebSocket alert handshake verified:', data.username, data.role);
            } else if (data.type === 'INCIDENT_CREATED') {
              const incident: Incident = data.incident;

              // Duplicate event protection: check bounded seen set
              if (recentIncidentIdsRef.current.has(incident.incident_id)) {
                return;
              }

              recentIncidentIdsRef.current.add(incident.incident_id);
              if (recentIncidentIdsRef.current.size > MAX_RECENT_INCIDENTS) {
                // Keep bounded memory size
                const first = recentIncidentIdsRef.current.values().next().value;
                if (first) recentIncidentIdsRef.current.delete(first);
              }

              // Play optional chime
              if (audioEnabled) {
                playAlertChime();
              }

              // Add toast alert
              const alertItem: ActiveAlert = {
                id: incident.incident_id,
                incident,
                receivedAt: new Date(),
              };

              setActiveAlerts((prev) => [alertItem, ...prev.slice(0, 4)]);

              // Notify subscribed page listeners
              createdListenersRef.current.forEach((listener) => {
                try {
                  listener(data);
                } catch (e) {
                  console.error('Error in incident created listener:', e);
                }
              });
            } else if (data.type === 'INCIDENT_UPDATED') {
              // Notify subscribed page listeners
              updatedListenersRef.current.forEach((listener) => {
                try {
                  listener(data);
                } catch (e) {
                  console.error('Error in incident updated listener:', e);
                }
              });
            } else if (data.type === 'PING') {
              // Respond with keepalive pong
              if (socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: 'PONG', timestamp: new Date().toISOString() }));
              }
            }
          } catch (err) {
            console.warn('Failed to parse incoming WebSocket message:', err);
          }
        };

        socket.onclose = (event) => {
          if (isDisposed) return;
          console.warn(`WebSocket closed (code=${event.code}, reason=${event.reason || 'None'})`);

          // Code 1008 = Policy Violation (Auth failure/expired)
          if (event.code === 1008 || event.code === 4001 || event.code === 4003) {
            console.error('WebSocket authentication rejected by server. Halting reconnection.');
            setConnectionStatus('OFFLINE');
            logout();
            return;
          }

          setConnectionStatus('RECONNECTING');

          // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
          const attempts = reconnectAttemptsRef.current;
          const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, attempts), RECONNECT_MAX_MS);
          reconnectAttemptsRef.current += 1;

          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, delay);
        };

        socket.onerror = (err) => {
          console.debug('WebSocket error encountered:', err);
          // onclose will trigger next step
        };
      } catch (err) {
        console.error('Failed to instantiate WebSocket:', err);
        setConnectionStatus('OFFLINE');
      }
    };

    connect();

    return () => {
      isDisposed = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Provider unmounting');
        wsRef.current = null;
      }
      setConnectionStatus('OFFLINE');
    };
  }, [isAuthenticated, token, audioEnabled, logout]);

  // Auto-dismiss alerts after 8 seconds
  useEffect(() => {
    if (activeAlerts.length === 0) return;

    const timer = setInterval(() => {
      const now = Date.now();
      setActiveAlerts((prev) => prev.filter((a) => now - a.receivedAt.getTime() < 8000));
    }, 1000);

    return () => clearInterval(timer);
  }, [activeAlerts]);

  return (
    <WebSocketContext.Provider
      value={{
        connectionStatus,
        activeAlerts,
        dismissAlert,
        audioEnabled,
        toggleAudio,
        subscribeIncidentCreated,
        subscribeIncidentUpdated,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = (): WebSocketContextType => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};
