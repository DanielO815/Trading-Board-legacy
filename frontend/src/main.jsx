/**
 * Entry Point der Applikation.
 * 
 * Rendert Root-Komponente in DOM-Element mit ID "root" unter Verwendung
 * von React 19 StrictMode für Entwicklungs-Warnungen.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
