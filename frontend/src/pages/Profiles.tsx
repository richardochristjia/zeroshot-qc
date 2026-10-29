import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { JSX } from 'react'
import {
  ApiError,
  NotFoundError,
  draftProfileFromSop,
  getProfile,
  listProfiles,
  putProfile,
  referenceImageUrl,
} from '../api.ts'
import type { ProductProfile } from '../api.ts'
import { Alert } from '../components/Alert.tsx'
import { Button } from '../components/Button.tsx'
import { Dialog } from '../components/Dialog.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { Field } from '../components/Field.tsx'
import { PageHeader } from '../components/PageHeader.tsx'
import { Panel, PanelHeader } from '../components/Panel.tsx'
import { fromForm, isDirty, promptLines, toForm, validateForm } from '../profile-form.ts'
import type { ProfileForm } from '../profile-form.ts'

type LoadStatus = 'loading' | 'ready'

function errorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail
  return fallback
}

const sortById = (list: ProductProfile[]): ProductProfile[] => [...list].sort((a, b) => a.id.localeCompare(b.id))

export default function Profiles(): JSX.Element {
  const [profiles, setProfiles] = useState<ProductProfile[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [form, setForm] = useState<ProfileForm | null>(null)
  const [isNew, setIsNew] = useState<boolean>(false)
  const [filter, setFilter] = useState<string>('')
  const [loadStatus, setLoadStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<boolean>(false)
  const [justSaved, setJustSaved] = useState<boolean>(false)
  const [badRef, setBadRef] = useState<string | null>(null)

  const [sopOpen, setSopOpen] = useState<boolean>(false)
  const [sopText, setSopText] = useState<string>('')
  const [sopCategory, setSopCategory] = useState<string>('')
  const [sopBusy, setSopBusy] = useState<boolean>(false)
  const [sopError, setSopError] = useState<string | null>(null)
  const sopAbort = useRef<AbortController | null>(null)

  const [existing, setExisting] = useState<ProductProfile | null>(null)
  const [replace, setReplace] = useState<boolean>(false)
  const [pending, setPending] = useState<(() => void) | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    listProfiles(controller.signal)
      .then((loaded) => {
        setProfiles(loaded)
        if (loaded.length > 0) {
          setSelectedId(loaded[0].id)
          setForm(toForm(loaded[0]))
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

  const savedProfile = isNew ? null : (profiles.find((p) => p.id === selectedId) ?? null)
  const saved = savedProfile === null ? null : toForm(savedProfile)
  const dirty = form !== null && isDirty(form, saved)
  const errors = form === null ? {} : validateForm(form, { checkId: isNew })
  const errorCount = Object.keys(errors).length
  const idError = errors.id ?? (existing !== null && !replace ? `Id “${existing.id}” already exists.` : undefined)
  const canSave = dirty && errorCount === 0 && !saving && !(existing !== null && !replace)

  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent): void => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const edit = (patch: Partial<ProfileForm>): void => {
    if (form === null) return
    setForm({ ...form, ...patch })
    setJustSaved(false)
    if ('id' in patch) {
      setExisting(null)
      setReplace(false)
    }
  }

  const open = (profile: ProductProfile | null, asNew: boolean): void => {
    setIsNew(asNew)
    setSelectedId(profile === null || asNew ? '' : profile.id)
    setForm(profile === null ? null : toForm(profile))
    setExisting(null)
    setReplace(false)
    setJustSaved(false)
    setError(null)
  }

  // Run an action now, or after the user confirms discarding edits.
  const guard = (action: () => void): void => {
    if (dirty) setPending(() => action)
    else action()
  }

  const handleReload = (): void => {
    setError(null)
    listProfiles()
      .then((loaded) => {
        setProfiles(loaded)
        open(loaded.find((p) => p.id === selectedId) ?? null, false)
      })
      .catch((err: unknown) => setError(errorDetail(err, 'Could not reload profiles.')))
  }

  const finishSave = (toSave: ProductProfile): Promise<void> =>
    putProfile(toSave).then((savedOne) => {
      setProfiles((prev) => sortById([...prev.filter((p) => p.id !== savedOne.id), savedOne]))
      open(savedOne, false)
      setJustSaved(true)
    })

  const handleSave = (): void => {
    if (form === null || !canSave) return
    setSaving(true)
    setError(null)
    const toSave = fromForm(form)
    const done = (): void => setSaving(false)
    const fail = (err: unknown): void => {
      setError(errorDetail(err, 'Could not save the profile.'))
      done()
    }
    if (!isNew || replace) {
      finishSave(toSave).catch(fail).finally(done)
      return
    }
    // PUT overwrites silently, so check existence first for a new draft.
    getProfile(toSave.id)
      .then((found) => {
        setExisting(found)
        done()
      })
      .catch((err: unknown) => {
        if (err instanceof NotFoundError) finishSave(toSave).catch(fail).finally(done)
        else fail(err)
      })
  }

  const saveRef = useRef(handleSave)
  useEffect(() => {
    saveRef.current = handleSave
  })
  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 's') return
      event.preventDefault()
      if (!sopOpen && pending === null) saveRef.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sopOpen, pending])

  const handleDraftFromSop = (): void => {
    if (sopText.trim() === '' || sopCategory.trim() === '' || sopBusy) return
    setSopBusy(true)
    setSopError(null)
    const controller = new AbortController()
    sopAbort.current = controller
    draftProfileFromSop({ sopText: sopText.trim(), categoryName: sopCategory.trim() }, controller.signal)
      .then((drafted) => {
        open(drafted, true)
        setSopOpen(false)
        setSopText('')
        setSopCategory('')
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setSopError(errorDetail(err, 'Could not draft a profile from the SOP text.'))
      })
      .finally(() => setSopBusy(false))
  }

  const discardDraft = (): void => {
    if (isNew) open(profiles.find((p) => p.id === selectedId) ?? profiles[0] ?? null, false)
    else if (saved !== null) setForm(saved)
    setJustSaved(false)
  }

  const needle = filter.trim().toLowerCase()
  const visible = profiles.filter((p) => needle === '' || p.name.toLowerCase().includes(needle) || p.id.toLowerCase().includes(needle))
  const fade = { initial: { opacity: 0, y: -4 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0 }, transition: { duration: 0.15 } }
  const dot = <span className="size-2 shrink-0 rounded-full bg-detect" role="img" aria-label="Unsaved changes" />
  const status =
    errorCount > 0
      ? `${errorCount} ${errorCount === 1 ? 'field needs' : 'fields need'} attention`
      : dirty
        ? 'Unsaved changes · ⌘S'
        : justSaved
          ? 'Saved'
          : 'No changes'
  const discardName = isNew ? null : (savedProfile?.name ?? 'this profile')

  return (
    <section aria-label="Profiles">
      <PageHeader title="Profiles" subtitle="What each product is checked for, and the rules the judge applies.">
        <Button icon="sparkles" onClick={() => guard(() => setSopOpen(true))} disabled={saving}>
          New from SOP
        </Button>
      </PageHeader>

      <AnimatePresence>
        {error !== null && (
          <motion.div key="err" {...fade} className="mb-4">
            <Alert>{error}</Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {loadStatus === 'loading' ? (
        <EmptyState title="Loading profiles…" />
      ) : profiles.length === 0 && !isNew ? (
        <EmptyState
          icon="sliders"
          title="No profiles yet."
          action={
            <Button icon="refresh" onClick={handleReload}>
              Reload
            </Button>
          }
        >
          Draft your first profile with New from SOP, or add a profile JSON file to the backend profiles directory and
          press Reload.
        </EmptyState>
      ) : (
        <div className="grid items-start gap-4 min-[1001px]:grid-cols-[260px_minmax(0,1fr)]">
          <Panel>
            <PanelHeader title={`${profiles.length} ${profiles.length === 1 ? 'profile' : 'profiles'}`}>
              <Button variant="ghost" icon="refresh" onClick={() => guard(handleReload)} disabled={saving} className="!min-h-8 !px-2">
                Reload
              </Button>
            </PanelHeader>
            <div className="border-b border-line p-2">
              <input
                type="search"
                className="ctl"
                aria-label="Filter profiles"
                placeholder="Filter by name or id"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
            </div>
            <ul>
              {isNew && form !== null && (
                <li className="border-b border-line">
                  <div
                    aria-current="true"
                    className="flex items-center justify-between gap-3 border-l-[3px] border-accent bg-sunken px-3 py-2.5 text-sm"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-ink">{form.name || 'Untitled'}</span>
                      <span className="block truncate font-mono text-xs text-ink-3">{form.id || 'new'}</span>
                    </span>
                    <span className="flex items-center gap-2 text-xs text-ink-3">
                      New {dot}
                    </span>
                  </div>
                </li>
              )}
              {visible.map((profile) => {
                const selected = !isNew && profile.id === selectedId
                return (
                  <li key={profile.id} className="border-b border-line last:border-b-0">
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => {
                        if (!selected) guard(() => open(profile, false))
                      }}
                      aria-current={selected ? 'true' : undefined}
                      className={`flex w-full items-center justify-between gap-3 border-l-[3px] px-3 py-2.5 text-left text-sm ${
                        selected ? 'border-accent bg-sunken' : 'border-transparent hover:bg-sunken'
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-ink">{profile.name}</span>
                        <span className="block truncate font-mono text-xs text-ink-3">{profile.id}</span>
                      </span>
                      <span className="num flex shrink-0 items-center gap-2 text-xs text-ink-3">
                        {selected && dirty && dot}
                        {profile.defectPrompts.length} prompts
                      </span>
                    </button>
                  </li>
                )
              })}
              {visible.length === 0 && <li className="px-3.5 py-3 text-sm text-ink-3">No profiles match.</li>}
            </ul>
          </Panel>

          <Panel>
            {form === null ? (
              <div className="p-3.5">
                <EmptyState icon="sliders" title="Select a profile">
                  Pick a profile on the left to edit it.
                </EmptyState>
              </div>
            ) : (
              <fieldset disabled={saving} className="contents">
                <PanelHeader title={form.name || 'Untitled'}>
                  {isNew ? (
                    <span className="rounded-sm border border-line px-1.5 py-0.5 text-xs font-medium text-ink-2">New</span>
                  ) : (
                    <span className="text-xs text-ink-3">
                      <span className="font-mono">{form.id}</span> · Ids are fixed once created
                    </span>
                  )}
                </PanelHeader>
                <div className="flex flex-col gap-4 p-3.5">
                  {isNew && (
                    <Alert kind="notice">
                      Drafted from SOP. Nothing is saved yet: review the fields, choose an id and press Save.
                    </Alert>
                  )}
                  {isNew && (
                    <>
                      <Field label="Id" hint="Letters, digits, - and _. Cannot change after saving." error={idError}>
                        <input
                          type="text"
                          className="ctl font-mono"
                          value={form.id}
                          onChange={(event) => edit({ id: event.target.value })}
                        />
                      </Field>
                      {existing !== null && (
                        <label className="flex items-center gap-2 text-sm text-ink-2">
                          <input type="checkbox" checked={replace} onChange={(event) => setReplace(event.target.checked)} />
                          Replace the existing profile “{existing.name}”
                        </label>
                      )}
                    </>
                  )}
                  <Field label="Name" error={errors.name}>
                    <input type="text" className="ctl" value={form.name} onChange={(event) => edit({ name: event.target.value })} />
                  </Field>
                  <Field
                    label={
                      <span className="flex items-baseline justify-between">
                        Defect prompts
                        <span className="num text-xs font-normal text-ink-3">{promptLines(form.prompts).length} prompts</span>
                      </span>
                    }
                    hint="What the segmenter looks for, one per line"
                    error={errors.prompts}
                  >
                    <textarea
                      className="ctl font-mono"
                      rows={4}
                      value={form.prompts}
                      onChange={(event) => edit({ prompts: event.target.value })}
                    />
                  </Field>
                  <Field label="Rules" hint="Plain English. The judge cites these when it fails a part.">
                    <textarea className="ctl" rows={4} value={form.rules} onChange={(event) => edit({ rules: event.target.value })} />
                  </Field>
                  <div className="grid gap-4 min-[641px]:grid-cols-3">
                    <Field label="mm per px" hint="Blank = report pixels only" error={errors.mmPerPx}>
                      <input
                        type="text"
                        inputMode="decimal"
                        className="ctl num"
                        value={form.mmPerPx}
                        onChange={(event) => edit({ mmPerPx: event.target.value })}
                      />
                    </Field>
                    <Field label="Min score" hint="Candidates below this are dropped" error={errors.minScore}>
                      <input
                        type="text"
                        inputMode="decimal"
                        className="ctl num"
                        value={form.minScore}
                        onChange={(event) => edit({ minScore: event.target.value })}
                      />
                    </Field>
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <Field
                          label="Reference image"
                          hint="Path under data/; blank = none"
                          error={
                            form.referenceImage.trim() !== '' && badRef === form.referenceImage.trim()
                              ? 'Image not found: the judge runs without a reference.'
                              : undefined
                          }
                        >
                          <input
                            type="text"
                            className="ctl"
                            value={form.referenceImage}
                            onChange={(event) => edit({ referenceImage: event.target.value })}
                          />
                        </Field>
                      </div>
                      {form.referenceImage.trim() !== '' &&
                        (badRef === form.referenceImage.trim() ? (
                          <span className="grid size-14 shrink-0 place-items-center rounded-sm border border-dashed border-line-strong text-center text-[10px] text-ink-3">
                            Not found
                          </span>
                        ) : (
                          <img
                            key={form.referenceImage.trim()}
                            src={referenceImageUrl(form.referenceImage.trim())}
                            alt=""
                            className="size-14 shrink-0 rounded-sm border border-line object-cover"
                            onError={() => setBadRef(form.referenceImage.trim())}
                          />
                        ))}
                    </div>
                  </div>
                </div>
                <div className="sticky bottom-0 flex flex-wrap items-center gap-3 rounded-b-md border-t border-line bg-surface px-3.5 py-2.5">
                  <Button
                    variant={existing !== null ? 'secondary' : 'primary'}
                    icon="save"
                    onClick={handleSave}
                    disabled={!canSave}
                    className={existing !== null ? '!border-fail !bg-fail !text-on-fail' : ''}
                  >
                    {saving ? 'Saving…' : existing !== null ? `Replace ${existing.id}` : 'Save profile'}
                  </Button>
                  {dirty && <Button onClick={discardDraft}>{isNew ? 'Discard draft' : 'Discard changes'}</Button>}
                  <span className="text-xs text-ink-3" role="status">
                    {status}
                  </span>
                </div>
              </fieldset>
            )}
          </Panel>
        </div>
      )}

      <Dialog
        open={sopOpen}
        title="New profile from SOP"
        onClose={() => {
          // The native dialog is already closed here, so drop any draft still in flight.
          sopAbort.current?.abort()
          setSopOpen(false)
        }}
      >
        <div className="flex flex-col gap-4 p-3.5">
          <p className="text-[13px] text-ink-2">
            Draft a profile from an SOP paragraph. Nothing is saved: you review the draft in the editor first.
          </p>
          <Field label="Category name">
            <input type="text" className="ctl" value={sopCategory} onChange={(event) => setSopCategory(event.target.value)} placeholder="bottle" />
          </Field>
          <Field label="SOP text">
            <textarea
              className="ctl"
              rows={6}
              value={sopText}
              onChange={(event) => setSopText(event.target.value)}
              placeholder="Paste the SOP paragraph describing defects and rules…"
            />
          </Field>
          {sopError !== null && <Alert>{sopError}</Alert>}
          <div>
            <Button
              variant="primary"
              icon="sparkles"
              onClick={handleDraftFromSop}
              disabled={sopText.trim() === '' || sopCategory.trim() === '' || sopBusy}
            >
              {sopBusy ? 'Drafting…' : 'Draft profile'}
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={pending !== null}
        title={discardName === null ? 'Discard the unsaved SOP draft?' : `Discard your changes to ${discardName}?`}
        onClose={() => setPending(null)}
      >
        <div className="flex flex-col gap-4 p-3.5">
          <p className="text-[13px] text-ink-2">Your edits have not been saved and will be lost.</p>
          <div className="flex gap-2">
            <Button onClick={() => setPending(null)}>Keep editing</Button>
            <Button
              variant="primary"
              onClick={() => {
                const run = pending
                setPending(null)
                run?.()
              }}
            >
              Discard changes
            </Button>
          </div>
        </div>
      </Dialog>
    </section>
  )
}
