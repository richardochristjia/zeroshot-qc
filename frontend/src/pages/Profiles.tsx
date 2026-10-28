import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { JSX } from 'react'
import {
  ApiError,
  NotFoundError,
  draftProfileFromSop,
  getProfile,
  listProfiles,
  putProfile,
} from '../api.ts'
import { resolveFileUrl } from '../api.ts'
import type { ProductProfile } from '../api.ts'
import { Alert } from '../components/Alert.tsx'
import { Button } from '../components/Button.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { Field } from '../components/Field.tsx'
import { PageHeader } from '../components/PageHeader.tsx'
import { Icon } from '../components/Icon.tsx'
import { Panel, PanelHeader } from '../components/Panel.tsx'

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
  const sopPanelRef = useRef<HTMLDivElement>(null)
  const sopCategoryRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const controller = new AbortController()
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

  const jumpToSop = (): void => {
    sopPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    sopCategoryRef.current?.focus({ preventScroll: true })
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

  const loaded = profiles.find((profile) => profile.id === selectedId) ?? null
  const dirty = draft !== null && loaded !== null && JSON.stringify(draft) !== JSON.stringify(loaded)
  const fade = { initial: { opacity: 0, y: -4 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0 }, transition: { duration: 0.15 } }

  return (
    <section aria-label="Profiles">
      <PageHeader title="Profiles" subtitle="What each product is checked for, and the rules the judge applies.">
        <Button icon="file" onClick={jumpToSop}>
          Draft from SOP
        </Button>
      </PageHeader>

      <AnimatePresence>
        {error !== null && (
          <motion.div key="err" {...fade} className="mb-4">
            <Alert>{error}</Alert>
          </motion.div>
        )}
        {notice !== null && (
          <motion.div key="notice" {...fade} className="mb-4">
            <Alert kind="notice">{notice}</Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {loadStatus === 'loading' ? (
        <EmptyState title="Loading profiles…" />
      ) : profiles.length === 0 ? (
        <EmptyState
          icon="sliders"
          title="No profiles yet."
          action={
            <Button icon="refresh" onClick={handleRefresh}>
              Reload
            </Button>
          }
        >
          Import your first profile from an SOP paragraph below, or add a profile JSON file to the backend
          profiles directory and press Reload.
        </EmptyState>
      ) : (
        <div className="grid items-start gap-4 min-[1001px]:grid-cols-[260px_minmax(0,1fr)]">
          <Panel>
            <PanelHeader title={`${profiles.length} ${profiles.length === 1 ? 'profile' : 'profiles'}`}>
              <Button variant="ghost" icon="refresh" onClick={handleRefresh} className="!min-h-8 !px-2">
                Reload
              </Button>
            </PanelHeader>
            <ul>
              {profiles.map((profile) => (
                <li key={profile.id} className="border-b border-line last:border-b-0">
                  <button
                    type="button"
                    onClick={() => selectProfile(profile.id)}
                    aria-current={profile.id === selectedId ? 'true' : undefined}
                    className={`flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left text-sm ${
                      profile.id === selectedId ? 'bg-sunken' : 'hover:bg-sunken'
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-ink">{profile.name}</span>
                      <span className="block truncate font-mono text-xs text-ink-3">{profile.id}</span>
                    </span>
                    <span className="num shrink-0 text-xs text-ink-3">{profile.defectPrompts.length} prompts</span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel>
            {draft === null ? (
              <div className="p-3.5">
                <EmptyState icon="sliders" title="Select a profile">
                  Pick a profile on the left to edit it.
                </EmptyState>
              </div>
            ) : (
              <>
                <PanelHeader title={draft.name || 'Untitled'}>
                  <span className="text-xs text-ink-3">
                    <span className="font-mono">{draft.id}</span> · Ids are fixed once created
                  </span>
                </PanelHeader>
                <div className="flex flex-col gap-4 p-3.5">
                  <Field label="Name">
                    <input
                      type="text"
                      className="ctl"
                      value={draft.name}
                      onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                    />
                  </Field>
                  <Field label="Defect prompts" hint="What the segmenter looks for, one per line">
                    <textarea
                      className="ctl font-mono"
                      rows={4}
                      value={promptsToText(draft.defectPrompts)}
                      onChange={(event) => setDraft({ ...draft, defectPrompts: textToPrompts(event.target.value) })}
                    />
                  </Field>
                  <Field label="Rules" hint="Plain English. The judge cites these when it fails a part.">
                    <textarea
                      className="ctl"
                      rows={4}
                      value={draft.rules}
                      onChange={(event) => setDraft({ ...draft, rules: event.target.value })}
                    />
                  </Field>
                  <div className="grid gap-4 min-[641px]:grid-cols-3">
                    <Field label="mm per px" hint="Blank = report pixels only">
                      <input
                        type="text"
                        inputMode="decimal"
                        className="ctl num"
                        value={draft.mmPerPx === null ? '' : String(draft.mmPerPx)}
                        onChange={(event) => setDraft({ ...draft, mmPerPx: parseNullableNumber(event.target.value) })}
                      />
                    </Field>
                    <Field label="Min score" hint="Candidates below this are dropped">
                      <input
                        type="number"
                        step="0.05"
                        min="0"
                        max="1"
                        className="ctl num"
                        value={draft.minScore}
                        onChange={(event) => {
                          const parsed = Number(event.target.value)
                          setDraft({ ...draft, minScore: Number.isNaN(parsed) ? 0 : parsed })
                        }}
                      />
                    </Field>
                    <Field label="Reference image" hint="Path; blank = none">
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          className="ctl"
                          value={draft.referenceImage ?? ''}
                          onChange={(event) =>
                            setDraft({
                              ...draft,
                              referenceImage: event.target.value.trim() === '' ? null : event.target.value.trim(),
                            })
                          }
                        />
                        {draft.referenceImage !== null && (
                          <img
                            src={resolveFileUrl(draft.referenceImage)}
                            alt=""
                            className="size-14 shrink-0 rounded-sm border border-line object-cover"
                            onError={(event) => {
                              event.currentTarget.style.visibility = 'hidden'
                            }}
                          />
                        )}
                      </div>
                    </Field>
                  </div>
                </div>
                <div className="flex items-center gap-3 border-t border-line px-3.5 py-2.5">
                  <Button variant="primary" icon="save" onClick={handleSaveEdit} disabled={saving || draft.name.trim() === ''}>
                    {saving ? 'Saving…' : 'Save profile'}
                  </Button>
                  {dirty && <span className="text-xs text-ink-3">Unsaved changes</span>}
                </div>
              </>
            )}
          </Panel>
        </div>
      )}

      <div ref={sopPanelRef} className="mt-4 scroll-mt-20">
      <Panel>
        <PanelHeader title={<><Icon name="file" />Import from SOP</>} />
        <div className="flex flex-col gap-4 p-3.5">
          <p className="text-[13px] text-ink-2">
            Draft a profile from an SOP paragraph. Drafting never saves anything: review the draft, then save it
            under a new id.
          </p>
          <Field label="Category name">
            <input
              ref={sopCategoryRef}
              type="text"
              className="ctl"
              value={sopCategory}
              onChange={(event) => setSopCategory(event.target.value)}
              placeholder="bottle"
            />
          </Field>
          <Field label="SOP text">
            <textarea
              className="ctl"
              rows={5}
              value={sopText}
              onChange={(event) => setSopText(event.target.value)}
              placeholder="Paste the SOP paragraph describing defects and rules…"
            />
          </Field>
          <div>
            <Button
              variant="primary"
              icon="sparkles"
              onClick={handleDraftFromSop}
              disabled={sopText.trim() === '' || sopCategory.trim() === '' || sopBusy}
            >
              {sopBusy && sopDraft === null ? 'Drafting…' : 'Draft from SOP'}
            </Button>
          </div>

          <AnimatePresence>
            {sopError !== null && (
              <motion.div key="serr" {...fade}>
                <Alert>{sopError}</Alert>
              </motion.div>
            )}
            {sopNotice !== null && (
              <motion.div key="snotice" {...fade}>
                <Alert kind="notice">{sopNotice}</Alert>
              </motion.div>
            )}
            {sopDraft !== null && (
              <motion.div key="draft" {...fade} className="rounded-md border border-line p-3.5">
                <h3 className="text-[13px] font-semibold text-ink-2">Draft preview</h3>
                <dl className="mt-2 space-y-1.5 text-sm">
                  <div className="flex gap-3">
                    <dt className="w-28 shrink-0 text-ink-3">Name</dt>
                    <dd>{sopDraft.name}</dd>
                  </div>
                  <div className="flex gap-3">
                    <dt className="w-28 shrink-0 text-ink-3">Suggested id</dt>
                    <dd className="font-mono text-xs">{sopDraft.id}</dd>
                  </div>
                  <div className="flex gap-3">
                    <dt className="w-28 shrink-0 text-ink-3">Rules</dt>
                    <dd>{sopDraft.rules}</dd>
                  </div>
                  <div className="flex gap-3">
                    <dt className="w-28 shrink-0 text-ink-3">Prompts</dt>
                    <dd>{sopDraft.defectPrompts.join(', ')}</dd>
                  </div>
                </dl>
                <div className="mt-4 flex flex-col gap-4">
                  <Field label="Save as id">
                    <input
                      type="text"
                      className="ctl font-mono"
                      value={saveAsId}
                      onChange={(event) => {
                        setSaveAsId(event.target.value)
                        setExistingProfile(null)
                        setOverwriteArmed(false)
                      }}
                    />
                  </Field>
                  <AnimatePresence>
                    {existingProfile !== null && !overwriteArmed && (
                      <motion.div key="overwrite" {...fade}>
                        <Alert>
                          <p>
                            Id <span className="font-mono font-medium">{existingProfile.id}</span> already exists (“
                            {existingProfile.name}”). Saving would overwrite it.
                          </p>
                          <Button className="mt-2" onClick={() => setOverwriteArmed(true)}>
                            I understand — overwrite this profile
                          </Button>
                        </Alert>
                      </motion.div>
                    )}
                  </AnimatePresence>
                  {overwriteArmed && (
                    <p className="text-sm font-medium text-fail">
                      Overwrite confirmed. Press save to replace the existing profile.
                    </p>
                  )}
                  <div>
                    <Button variant="primary" icon="save" onClick={handleSaveDraftAsNew} disabled={saveAsId.trim() === '' || sopBusy}>
                      {sopBusy ? 'Saving…' : overwriteArmed ? 'Overwrite existing profile' : 'Save as new profile'}
                    </Button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Panel>
      </div>
    </section>
  )
}
