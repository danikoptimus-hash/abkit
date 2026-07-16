import type { ReactNode } from 'react'

// Bug fix (Datasets delete-confirm modal): AntD's <Modal> renders via a
// React portal (into document.body), so it sits OUTSIDE any table in the
// DOM tree — but React's synthetic event system bubbles clicks according
// to the REACT COMPONENT TREE, not the DOM tree. A modal that's a
// component-tree descendant of a table row (e.g. rendered inline inside a
// column's render() — Datasets.tsx's per-row delete action used to do
// this) still has its clicks reach that row's onClick, even though visually
// the modal is floating in front of everything. Concretely: clicking into
// the "type DELETE to confirm" input also "clicked" the row underneath and
// opened its preview drawer, stealing focus mid-type.
//
// AntD's own onCancel/onOk callbacks already get a stoppable event, so the
// header close button/mask-click/footer buttons were already safe IF the
// call site remembered to call e.stopPropagation() there (Datasets.tsx did)
// — but that leaves every other interactive element in the modal BODY
// (inputs, selects, ...) unprotected, and is easy to forget for new
// content. Wrapping a modal's `children` in this component stops
// propagation for the whole body in one place instead of hunting down
// every element — apply it to any modal that can be open while a table
// with row-level interactivity (onRow, or a clickable name link) is
// rendered behind it, not just ones with a currently-known bug: cheap
// insurance, and correct even if the table gains an onRow handler later.
export function StopClickPropagation({ children }: { children: ReactNode }) {
  return <div onClick={(e) => e.stopPropagation()}>{children}</div>
}
