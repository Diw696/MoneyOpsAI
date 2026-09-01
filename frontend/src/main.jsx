import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import PrimitivesShowcase from './PrimitivesShowcase.jsx'

// Phase 3 dev-only surface: #showcase renders the isolated primitive
// showcase instead of the real app. Chosen at mount time, before App's own
// state/data-loading effects ever run, so the showcase is fully isolated
// from production data and never touches a real page.
const isShowcase = typeof window !== 'undefined' && window.location.hash === '#showcase';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isShowcase ? <PrimitivesShowcase /> : <App />}
  </StrictMode>,
)
