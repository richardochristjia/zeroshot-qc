import { useCallback, useEffect, useState } from 'react'
import type { JSX } from 'react'
import {
  ApiError,
  NotFoundError,
  draftProfileFromSop,
  getProfile,
  listProfiles,
  putProfile,
} from '../api.ts'
import type { ProductProfile } from '../api.ts'

type LoadStatus = 'loading' | 'ready'

function errorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail
  return fallback
}

function promptsToText(prompts: string[]): string {
  return prompts.join('\n')
}

function textToPrompts(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

function parseNullableNumber(text: string): number | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  const parsed = Number(trimmed)
  return Number.isNaN(parsed) ? null : parsed
}

export default function Profiles(): JSX.Element {
  const [profiles, setProfiles] = useState<ProductProfile[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [draft, setDraft] = useState<ProductProfile | null>(null)
  const [loadStatus, setLoadStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [saving, setSaving] = useState<boolean>(false)

  const [sopText, setSopText] = useState<string>('')
  const [sopCategory, setSopCategory] = useState<string>('')
  const [sopDraft, setSopDraft] = useState<ProductProfile | null>(null)
  const [saveAsId, setSaveAsId] = useState<string>('')
  const [sopBusy, setSopBusy] = useState<boolean>(false)
  const [sopError, setSopError] = useState<string | null>(null)
  const [sopNotice, setSopNotice] = useState<string | null>(null)
  const [existingProfile, setExistingProfile] = useState<ProductProfile | null>(null)
  const [overwriteArmed, setOverwriteArmed] = useState<boolean>(false)

  useEffect(() => {
    const controller = new AbortController()
    setLoadStatus('loading')
    listProfiles(controller.signal)
      .then((loaded) => {
        setProfiles(loaded)
        if (loaded.length > 0) {
          setSelectedId(loaded[0].id)
          setDraft(loaded[0])
        }
        setLoadStatus('ready')
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(errorDetail(err, 'Could not load profiles.'))
        setLoadStatus('ready')
      })
    return () => controller.abort()
  }, [])

  const selectProfile = useCallback(
    (id: string): void => {
      setSelectedId(id)
      setNotice(null)
      setError(null)
      const found = profiles.find((profile) => profile.id === id) ?? null
      setDraft(found)
    },
    [profiles],
  )

  const refreshList = useCallback(async (): Promise<void> => {
    const loaded = await listProfiles()
    setProfiles(loaded)
    return
  }, [])

  const handleSaveEdit = (): void => {
    if (draft === null || saving) return
    setSaving(true)
    setError(null)
    setNotice(null)
    putProfile(draft)
      .then((saved) => {
        setProfiles((prev) =>
          prev.some((profile) => profile.id === saved.id)
            ? prev.map((profile) => (profile.id === saved.id ? saved : profile))
            : [...prev, saved].sort((a, b) => a.id.localeCompare(b.id)),
        )
        setDraft(saved)
        setNotice(`Saved profile “${saved.id}”.`)
      })
      .catch((err: unknown) => {
        setError(errorDetail(err, 'Could not save the profile.'))
      })
      .finally(() => setSaving(false))
  }

  const handleDraftFromSop = (): void => {
    if (sopText.trim() === '' || sopCategory.trim() === '' || sopBusy) return
    setSopBusy(true)
    setSopError(null)
    setSopNotice(null)
    setExistingProfile(null)
    setOverwriteArmed(false)
    draftProfileFromSop({ sopText: sopText.trim(), categoryName: sopCategory.trim() })
      .then((drafted) => {
        setSopDraft(drafted)
        setSaveAsId(drafted.id)
      })
      .catch((err: unknown) => {
        setSopDraft(null)
        setSopError(errorDetail(err, 'Could not draft a profile from the SOP text.'))
      })
      .finally(() => setSopBusy(false))
  }

  const handleSaveDraftAsNew = (): void => {
    if (sopDraft === null || sopBusy) return
    const targetId = saveAsId.trim()
    if (targetId === '') {
      setSopError('Choose an id to save the draft under.')
      return
    }
    // PUT overwrites silently, so check existence first when not confirmed.
    if (!overwriteArmed) {
      setSopBusy(true)
      setSopError(null)
      setSopNotice(null)
      getProfile(targetId)
        .then((existing) => {
          // An id already exists: stop and ask for explicit confirmation.
          setExistingProfile(existing)
          setSopBusy(false)
        })
        .catch((err: unknown) => {
          if (err instanceof NotFoundError) {
            persistDraft(targetId)
            return
          }
          setSopError(errorDetail(err, 'Could not check whether that id exists.'))
          setSopBusy(false)
        })
      return
    }
    setSopBusy(true)
    setSopError(null)
    setSopNotice(null)
    persistDraft(targetId)
  }

  const persistDraft = (targetId: string): void => {
    if (sopDraft === null) {
      setSopBusy(false)
      return
    }
    const toSave: ProductProfile = { ...sopDraft, id: targetId }
    putProfile(toSave)
      .then((saved) => {
        setProfiles((prev) =>
          prev.some((profile) => profile.id === saved.id)
            ? prev.map((profile) => (profile.id === saved.id ? saved : profile))
            : [...prev, saved].sort((a, b) => a.id.localeCompare(b.id)),
        )
        setSelectedId(saved.id)
        setDraft(saved)
        setSopDraft(null)
        setSaveAsId('')
        setExistingProfile(null)
        setOverwriteArmed(false)
        setSopText('')
        setSopCategory('')
        setSopNotice(`Saved new profile “${saved.id}”.`)
      })
      .catch((err: unknown) => {
        setSopError(errorDetail(err, 'Could not save the drafted profile.'))
      })
      .finally(() => setSopBusy(false))
  }

  const handleRefresh = (): void => {
    setError(null)
    refreshList()
      .then(() => {
        setProfiles((prev) => {
          const stillThere = prev.find((profile) => profile.id === selectedId) ?? null
          setDraft(stillThere)
          return prev
        })
      })
      .catch((err: unknown) => {
        setError(errorDetail(err, 'Could not reload profiles.'))
      })
  }

  return (
    <section aria-label="Profiles">
      <h1 className="text-xl font-semibold">Profiles</h1>
      <p className="mt-2 text-sm">List, edit, and import product profiles.</p>

      {error !== null && (
        <p role="alert" className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}
      {notice !== null && (
        <p role="status" className="mt-3 rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
          {notice}
        </p>
      )}

      {loadStatus === 'loading' ? (
        <p role="status" className="mt-6 text-sm text-neutral-500">
          Loading profiles…
        </p>
      ) : profiles.length === 0 ? (
        <div className="mt-6 rounded border border-dashed border-neutral-300 px-4 py-10 text-center">
          <p className="text-sm font-medium text-neutral-700">No profiles yet.</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-neutral-500">
            Import your first profile from an SOP paragraph below, or add a profile JSON
            file to the backend profiles directory and press Reload.
          </p>
          <button
            type="button"
            onClick={handleRefresh}
            className="mt-4 rounded border border-neutral-300 bg-white px-4 py-1.5 text-sm font-medium"
          >
            Reload
          </button>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-[240px_1fr]">
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">All profiles</h2>
              <button
                type="button"
                onClick={handleRefresh}
                className="rounded border border-neutral-300 bg-white px-2 py-0.5 text-xs font-medium"
              >
                Reload
              </button>
            </div>
            <ul className="mt-2 space-y-1">
              {profiles.map((profile) => (
                <li key={profile.id}>
                  <button
                    type="button"
                    onClick={() => selectProfile(profile.id)}
                    aria-current={profile.id === selectedId ? 'true' : undefined}
                    className={`block w-full rounded border px-3 py-2 text-left text-sm ${
                      profile.id === selectedId
                        ? 'border-neutral-900 bg-neutral-900 text-white'
                        : 'border-neutral-300 bg-white hover:border-neutral-500'
                    }`}
                  >
                    <span className="block font-medium">{profile.name}</span>
                    <span className={`block text-xs ${profile.id === selectedId ? 'text-neutral-300' : 'text-neutral-500'}`}>
                      {profile.id}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h2 className="text-sm font-semibold">Edit profile</h2>
            {draft === null ? (
              <p className="mt-2 text-sm text-neutral-500">
                Select a profile on the left to edit it.
              </p>
            ) : (
              <div className="mt-2 rounded border border-neutral-300 px-4 py-3">
                <p className="text-xs text-neutral-500">
                  Editing <span className="font-mono font-medium">{draft.id}</span> — ids
                  are fixed; saving writes via PUT.
                </p>
                <label className="mt-3 flex flex-col gap-1 text-sm font-medium">
                  Name
                  <input
                    type="text"
                    value={draft.name}
                    onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm font-normal"
                  />
                </label>
                <label className="mt-3 flex flex-col gap-1 text-sm font-medium">
                  Defect prompts <span className="font-normal text-neutral-500">(one per line)</span>
                  <textarea
                    value={promptsToText(draft.defectPrompts)}
                    onChange={(event) =>
                      setDraft({ ...draft, defectPrompts: textToPrompts(event.target.value) })
                    }
                    rows={4}
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm font-normal"
                  />
                </label>
                <label className="mt-3 flex flex-col gap-1 text-sm font-medium">
                  Rules
                  <textarea
                    value={draft.rules}
                    onChange={(event) => setDraft({ ...draft, rules: event.target.value })}
                    rows={4}
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm font-normal"
                  />
                </label>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <label className="flex flex-col gap-1 text-sm font-medium">
                    mm per px <span className="font-normal text-neutral-500">(blank = none)</span>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={draft.mmPerPx === null ? '' : String(draft.mmPerPx)}
                      onChange={(event) =>
                        setDraft({ ...draft, mmPerPx: parseNullableNumber(event.target.value) })
                      }
                      className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm font-normal"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm font-medium">
                    Min score
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={draft.minScore}
                      onChange={(event) => {
                        const parsed = Number(event.target.value)
                        setDraft({ ...draft, minScore: Number.isNaN(parsed) ? 0 : parsed })
                      }}
                      className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm font-normal"
                    />
                  </label>
                </div>
                <label className="mt-3 flex flex-col gap-1 text-sm font-medium">
                  Reference image <span className="font-normal text-neutral-500">(blank = none)</span>
                  <input
                    type="text"
                    value={draft.referenceImage ?? ''}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        referenceImage:
                          event.target.value.trim() === '' ? null : event.target.value.trim(),
                      })
                    }
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm font-normal"
                  />
                </label>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  disabled={saving || draft.name.trim() === ''}
                  className="mt-4 rounded bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
                >
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-8">
        <h2 className="text-sm font-semibold">Import from SOP</h2>
        <p className="mt-1 text-sm text-neutral-600">
          Draft a profile from an SOP paragraph. Drafting never saves anything — review
          the draft, then save it under a new id.
        </p>
        <div className="mt-2 grid gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Category name
            <input
              type="text"
              value={sopCategory}
              onChange={(event) => setSopCategory(event.target.value)}
              placeholder="bottle"
              className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            SOP text
            <textarea
              value={sopText}
              onChange={(event) => setSopText(event.target.value)}
              rows={5}
              placeholder="Paste the SOP paragraph describing defects and rules…"
              className="rounded border border-neutral-300 bg-white px-3 py-2 text-sm font-normal"
            />
          </label>
          <div>
            <button
              type="button"
              onClick={handleDraftFromSop}
              disabled={sopText.trim() === '' || sopCategory.trim() === '' || sopBusy}
              className="rounded bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            >
              {sopBusy && sopDraft === null ? 'Drafting…' : 'Draft from SOP'}
            </button>
          </div>
        </div>

        {sopError !== null && (
          <p role="alert" className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
            {sopError}
          </p>
        )}
        {sopNotice !== null && (
          <p role="status" className="mt-3 rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
            {sopNotice}
          </p>
        )}

        {sopDraft !== null && (
          <div className="mt-4 rounded border border-neutral-300 px-4 py-3">
            <h3 className="text-sm font-semibold">Draft preview</h3>
            <dl className="mt-2 space-y-1 text-sm">
              <div className="flex gap-2">
                <dt className="w-28 shrink-0 font-medium text-neutral-600">Name</dt>
                <dd>{sopDraft.name}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-28 shrink-0 font-medium text-neutral-600">Suggested id</dt>
                <dd className="font-mono text-xs">{sopDraft.id}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-28 shrink-0 font-medium text-neutral-600">Rules</dt>
                <dd className="text-neutral-800">{sopDraft.rules}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-28 shrink-0 font-medium text-neutral-600">Prompts</dt>
                <dd>{sopDraft.defectPrompts.join(', ')}</dd>
              </div>
            </dl>
            <label className="mt-3 flex flex-col gap-1 text-sm font-medium">
              Save as id
              <input
                type="text"
                value={saveAsId}
                onChange={(event) => {
                  setSaveAsId(event.target.value)
                  setExistingProfile(null)
                  setOverwriteArmed(false)
                }}
                className="rounded border border-neutral-300 bg-white px-2 py-1 font-mono text-sm font-normal"
              />
            </label>
            {existingProfile !== null && !overwriteArmed && (
              <div role="alert" className="mt-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <p>
                  Id <span className="font-mono font-medium">{existingProfile.id}</span>{' '}
                  already exists (“{existingProfile.name}”). Saving would overwrite it.
                </p>
                <button
                  type="button"
                  onClick={() => setOverwriteArmed(true)}
                  className="mt-2 rounded border border-amber-600 px-3 py-1 text-sm font-medium text-amber-900"
                >
                  I understand — overwrite this profile
                </button>
              </div>
            )}
            {overwriteArmed && (
              <p className="mt-2 text-sm font-medium text-amber-900">
                Overwrite confirmed. Press save to replace the existing profile.
              </p>
            )}
            <button
              type="button"
              onClick={handleSaveDraftAsNew}
              disabled={saveAsId.trim() === '' || sopBusy}
              className="mt-3 rounded bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            >
              {sopBusy ? 'Saving…' : overwriteArmed ? 'Overwrite existing profile' : 'Save as new profile'}
            </button>
          </div>
        )}
      </div>
    </section>
  )
}
