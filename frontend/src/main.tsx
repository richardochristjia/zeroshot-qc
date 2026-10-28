import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MotionConfig, MotionGlobalConfig } from 'motion/react'
import '@fontsource/fira-sans/400.css'
import '@fontsource/fira-sans/500.css'
import '@fontsource/fira-sans/600.css'
import '@fontsource/fira-code/400.css'
import '@fontsource/fira-code/500.css'
import './index.css'
import App from './App.tsx'

// reducedMotion="user" keeps opacity fades; skip every animation instead.
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
MotionGlobalConfig.skipAnimations = reduced.matches
reduced.addEventListener('change', () => { MotionGlobalConfig.skipAnimations = reduced.matches })

const root = document.getElementById('root')
if (root === null) {
  throw new Error('Missing #root element')
}

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <MotionConfig reducedMotion="user">
        <App />
      </MotionConfig>
    </BrowserRouter>
  </StrictMode>,
)
