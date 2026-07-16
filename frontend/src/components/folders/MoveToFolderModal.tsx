import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Modal, Select, message } from 'antd'
import { apiClient, errorMessage } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'

const UNCATEGORIZED = '__uncategorized__'

// Row action AND bulk action (item 5, folders package) share this one modal
// — `names.length === 1` picks the single-experiment PUT endpoint,
// otherwise the bulk endpoint (same shape as BulkDeleteModal's "one names[]
// covers row and bulk" pattern). The experiments table has no `onRow`
// handler (unlike Datasets.tsx), so this Modal — a page-level sibling, not
// nested inside a row's render() — isn't exposed to the click-bubbling bug
// class fixed in item 3; no StopClickPropagation needed here.
export function MoveToFolderModal({
  names, onCancel, onDone,
}: {
  names: string[] | null
  onCancel: () => void
  onDone: () => void
}) {
  const [folderId, setFolderId] = useState<string | undefined>(undefined)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setFolderId(undefined)
  }, [names])

  const { data } = useQuery({
    queryKey: queryKeys.folders(),
    enabled: names !== null,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/folders')
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  const options = [
    { value: UNCATEGORIZED, label: 'Uncategorized' },
    ...(data?.items ?? []).map((f) => ({ value: f.id, label: f.name })),
  ]

  const handleMove = async () => {
    if (!names || !folderId) return
    setSaving(true)
    const targetFolderId = folderId === UNCATEGORIZED ? null : folderId
    try {
      if (names.length === 1) {
        const { error } = await apiClient.PUT('/api/v1/experiments/{name}/folder', {
          params: { path: { name: names[0] } },
          body: { folder_id: targetFolderId },
        })
        if (error) throw new Error(errorMessage(error))
        message.success('Moved')
      } else {
        const { data: result, error } = await apiClient.POST('/api/v1/experiments/bulk-move-folder', {
          body: { names, folder_id: targetFolderId },
        })
        if (error) throw new Error(errorMessage(error))
        if (result.skipped.length === 0) {
          message.success(`Moved ${result.moved.length} test${result.moved.length === 1 ? '' : 's'}`)
        } else {
          message.warning(
            `Moved ${result.moved.length}, skipped ${result.skipped.length} (no permission): ` +
              result.skipped.map((s) => s.name).join(', '),
          )
        }
      }
      onDone()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Failed to move')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={names && names.length > 1 ? `Move ${names.length} tests to folder` : 'Move to folder'}
      open={names !== null}
      onCancel={onCancel}
      onOk={handleMove}
      okText="Move"
      okButtonProps={{ disabled: !folderId, loading: saving }}
      destroyOnHidden
    >
      <Select
        style={{ width: '100%' }}
        placeholder="Select folder"
        aria-label="Target folder"
        options={options}
        value={folderId}
        onChange={setFolderId}
        autoFocus
      />
    </Modal>
  )
}
