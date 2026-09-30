import { Incident } from '../types/incident';

export type WebSocketEventType =
  | 'CONNECTED'
  | 'INCIDENT_CREATED'
  | 'INCIDENT_UPDATED'
  | 'PING'
  | 'PONG';

export interface ConnectedPayload {
  type: 'CONNECTED';
  timestamp: string;
  user_id: string;
  username: string;
  role: string;
}

export interface IncidentCreatedPayload {
  type: 'INCIDENT_CREATED';
  timestamp: string;
  incident: Incident;
}

export interface IncidentUpdatedPayload {
  type: 'INCIDENT_UPDATED';
  timestamp: string;
  incident_id: string;
  status: string;
  notes?: string;
  updated_at?: string;
  updated_by?: string;
}

export interface PingPongPayload {
  type: 'PING' | 'PONG';
  timestamp: string;
}

export type WebSocketAlertEvent =
  | ConnectedPayload
  | IncidentCreatedPayload
  | IncidentUpdatedPayload
  | PingPongPayload;

export type ConnectionStatus = 'CONNECTED' | 'RECONNECTING' | 'OFFLINE';

export interface ActiveAlert {
  id: string;
  incident: Incident;
  receivedAt: Date;
}
