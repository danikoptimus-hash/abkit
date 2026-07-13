import { createContext, useContext, useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'
import { useBlocker } from 'react-router-dom'
import { Modal } from 'antd'

// UX contract, part A: a single mechanism for "don't silently lose typed
// input" everywhere in the app — every form/modal/wizard that can lose data
// on navigation calls useUnsavedGuard(isDirty) with its own dirty check (a
// comparison against a pristine snapshot, computed by the caller — this
// hook has no opinion on what "dirty" means for a given form). Replaces
// three previously separate hand-rolled copies of the same
// isDirty+Modal.confirm pattern (ExperimentPage.tsx,
// ExperimentPropertiesModal.tsx, EditDatasetModal.tsx) that had each
// drifted slightly (e.g. only one of the three wired up beforeunload).
//
// Covers all three loss scenarios from the spec:
// - tab close/reload -> beforeunload (native, works under any router mode)
// - in-app ROUTE navigation (nav links, browser back/forward, navigate())
//   -> react-router's useBlocker, which requires a data router
//   (createBrowserRouter + <RouterProvider>, see main.tsx) — plain
//   <BrowserRouter> can't intercept this at all.
// - in-app NON-route actions (switching tabs within a page, closing a modal
//   via X/mask/Cancel, clicking an in-page link that doesn't change route)
//   -> the returned `guard(action)` wrapper: callers route every such action
//   through it instead of calling it directly.
//
// react-router's data router supports only ONE active useBlocker call at a
// time app-wide (confirmed empirically: a second simultaneous call logs "A
// router only supports one blocker at a time" and one of them silently
// stops working) — and this app routinely has several guarded components
// mounted at once (e.g. ExperimentPage's own edit-guard plus
// ExperimentPropertiesModal, always mounted alongside it just with
// open=false). So there is exactly ONE useBlocker call in the whole app,
// here in UnsavedGuardProvider (mounted once, in AppLayout) — every
// useUnsavedGuard() call registers its own dirty flag with it via context
// instead of calling useBlocker itself.

interface GuardContextValue {
  setDirty: (id: string, dirty: boolean) => void
}

const GuardContext = createContext<GuardContextValue | null>(null)

export function UnsavedGuardProvider({ children }: { children: ReactNode }) {
  // A Set of ids currently reporting dirty=true, not a single boolean — more
  // than one guarded component can be mounted (and even dirty) at once, and
  // one clearing itself (e.g. a modal closing after its own save) must not
  // clear another's still-outstanding dirty state.
  const dirtyIdsRef = useRef(new Set<string>())

  const setDirty = (id: string, dirty: boolean) => {
    if (dirty) dirtyIdsRef.current.add(id)
    else dirtyIdsRef.current.delete(id)
  }

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirtyIdsRef.current.size > 0 && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (blocker.state !== 'blocked') return
    Modal.confirm({
      title: 'You have unsaved changes',
      content: 'Discard them?',
      okText: 'Discard',
      okButtonProps: { danger: true },
      cancelText: 'Keep editing',
      onOk: () => blocker.proceed(),
      onCancel: () => blocker.reset(),
    })
  }, [blocker])

  return <GuardContext.Provider value={{ setDirty }}>{children}</GuardContext.Provider>
}

export function useUnsavedGuard(isDirty: boolean) {
  const ctx = useContext(GuardContext)
  const id = useId()

  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  // Registers/updates this instance's dirty flag with the single shared
  // blocker on every isDirty change, and clears it on unmount — a guarded
  // component that unmounts while dirty (e.g. a modal force-closed some
  // other way) must not leave a stale "dirty" entry blocking navigation
  // forever.
  useEffect(() => {
    ctx?.setDirty(id, isDirty)
    return () => ctx?.setDirty(id, false)
  }, [ctx, id, isDirty])

  const guard = (action: () => void) => {
    if (!isDirty) {
      action()
      return
    }
    Modal.confirm({
      title: 'You have unsaved changes',
      content: 'Discard them?',
      okText: 'Discard',
      okButtonProps: { danger: true },
      cancelText: 'Keep editing',
      onOk: action,
    })
  }

  // For a caller that knows it just saved (e.g. a multi-step wizard
  // navigating away right after successful submission) and needs the very
  // next navigate() call to go through unprompted, before isDirty itself
  // has a chance to become false through the caller's own state update (no
  // render happens between "just submitted" and the immediately-following
  // navigate() call in that flow) — clears this instance's entry in the
  // shared registry synchronously, outside any render/effect cycle.
  const markSaved = () => {
    ctx?.setDirty(id, false)
  }

  return { guard, markSaved }
}
