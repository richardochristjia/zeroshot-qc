import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { motion } from 'motion/react'
import { HealthDot } from './components/HealthDot.tsx'
import { Icon, IconSprite, type IconName } from './components/Icon.tsx'
import { ThemeSwitch } from './components/ThemeSwitch.tsx'
import Eval from './pages/Eval.tsx'
import Inspect from './pages/Inspect.tsx'
import Line from './pages/Line.tsx'
import Profiles from './pages/Profiles.tsx'
import Synthetic from './pages/Synthetic.tsx'

const links: { to: string; label: string; icon: IconName }[] = [
  { to: '/', label: 'Inspect', icon: 'scan' },
  { to: '/line', label: 'Line', icon: 'camera' },
  { to: '/profiles', label: 'Profiles', icon: 'sliders' },
  { to: '/eval', label: 'Eval', icon: 'chart' },
  { to: '/synthetic', label: 'Synthetic', icon: 'sparkles' },
]

export default function App() {
  const { pathname } = useLocation()
  return (
    <>
      <IconSprite />
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-x-6 border-b border-line bg-surface px-5 max-[640px]:px-4">
        <div className="flex h-[52px] items-center gap-2 whitespace-nowrap text-[15px] font-semibold">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.8" aria-hidden="true">
            <circle cx="12" cy="12" r="8" />
            <circle cx="12" cy="12" r="2.2" fill="var(--accent)" stroke="none" />
            <path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4" />
          </svg>
          <span className="max-[640px]:hidden">ZeroShot QC</span>
        </div>
        <nav aria-label="Main" className="flex h-[52px] gap-0.5 max-[640px]:order-3 max-[640px]:-mx-3 max-[640px]:h-10 max-[640px]:basis-full max-[640px]:px-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                `relative inline-flex items-center gap-1.5 px-3 text-sm no-underline ${isActive ? 'font-medium text-ink' : 'text-ink-2 hover:text-ink'}`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon name={link.icon} className={isActive ? 'text-ink' : 'text-ink-3'} />
                  {link.label}
                  {isActive && (
                    <motion.span layoutId="tab-underline" className="absolute inset-x-0 bottom-0 h-0.5 bg-ink" />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <HealthDot />
          <ThemeSwitch />
        </div>
      </header>
      <main className="mx-auto max-w-[1360px] px-5 pb-16 pt-5 max-[640px]:px-4">
        <motion.div key={pathname} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }}>
        <Routes>
          <Route path="/" element={<Inspect />} />
          <Route path="/line" element={<Line />} />
          <Route path="/profiles" element={<Profiles />} />
          <Route path="/eval" element={<Eval />} />
          <Route path="/synthetic" element={<Synthetic />} />
        </Routes>
        </motion.div>
      </main>
    </>
  )
}
