import type { JSX } from 'react'

export default function Inspect(): JSX.Element {
  return (
    <section>
      <h1 className="text-xl font-semibold">Inspect</h1>
      <p className="mt-2 text-sm">Upload an image and pick a profile to run an inspection.</p>
    </section>
  )
}
