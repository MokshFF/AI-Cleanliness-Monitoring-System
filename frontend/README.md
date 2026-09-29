# Cleanliness Monitoring System - Admin Web Dashboard

This directory houses the React + TypeScript frontend dashboard for the AI-Based National Cleanliness Monitoring System.

## Architecture (Implemented in Phase 7)
- **Framework**: React 18+ with TypeScript
- **Bundler**: Vite
- **UI & Styling**: Modern responsive component design (Tailwind CSS or modular CSS)
- **Routing**: React Router
- **Real-Time Data**: Native WebSocket client connected to FastAPI WebSocket endpoint
- **Maps**: Leaflet + OpenStreetMap for live camera markers and incident heatmaps
- **Analytics & Charts**: Recharts for violation breakdowns, hourly trends, and camera compliance
- **State Management**: React Context / Hooks

## Dashboard Features
1. **Admin Authentication**: JWT login and session persistence.
2. **Overview Dashboard**: High-level KPI cards (Active Incidents, Cleanliness Index, Online Cameras, Critical Violations).
3. **Live Camera Monitoring**: Low-latency video preview grid with status indicators.
4. **Real-Time WebSocket Alerts**: Instant notification banners and sound alerts on violation confirmation.
5. **Interactive Map**: Geolocation pins for all cameras with colored incident alert rings.
6. **Incident Management**: Detailed table with filtering, search, severity badges, snapshot preview modal, and status updates (NEW -> ACKNOWLEDGED -> RESOLVED).
7. **Analytics & Reports**: Historical statistics, category distributions, exportable reports.
