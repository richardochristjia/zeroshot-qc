import { NavLink, Route, Routes } from 'react-router-dom'
import Eval from './pages/Eval.tsx'
import Inspect from './pages/Inspect.tsx'
import Profiles from './pages/Profiles.tsx'
import Synthetic from './pages/Synthetic.tsx'

const links = [
  { to: '/', label: 'Inspect' },
  { to: '/profiles', label: 'Profiles' },
  { to: '/eval', label: 'Eval' },
  { to: '/synthetic', label: 'Synthetic' },
]

export default function App() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header>
        <h1 className="text-2xl font-bold">ZeroShot QC</h1>
        <nav className="mt-3 flex gap-4 border-b border-neutral-300 pb-2">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `text-sm font-medium ${isActive ? 'text-neutral-900 underline' : 'text-neutral-600'}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mt-6">
        <Routes>
          <Route path="/" element={<Inspect />} />
          <Route path="/profiles" element={<Profiles />} />
          <Route path="/eval" element={<Eval />} />
          <Route path="/synthetic" element={<Synthetic />} />
        </Routes>
      </main>
    </div>
  )
}
