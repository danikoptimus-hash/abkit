import { useEffect, useState } from 'react'
import { Modal, Typography, Form, Input, List } from 'antd'
import { apiClient, errorMessage } from '../api/client'

export interface BulkDeleteResult {
  deleted: string[]
  skipped: { name: string; reason: string }[]
}

interface Props {
  names: string[] | null
  onCancel: () => void
  onDone: (result: BulkDeleteResult) => void
}

// One shared confirmation modal for deleting several experiments at once
// (UX package, list п.E.4) — same "type DELETE to confirm" pattern as the
// single-experiment delete modal, but lists every selected name and warns
// about the total blast radius up front.
export function BulkDeleteModal({ names, onCancel, onDone }: Props) {
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setConfirmText('')
    setError(null)
  }, [names])

  const handleDelete = async () => {
    if (!names) return
    setDeleting(true)
    setError(null)
    try {
      const { data, error } = await apiClient.POST('/api/v1/experiments/bulk-delete', {
        body: { names, confirm: confirmText },
      })
      if (error) throw new Error(errorMessage(error))
      onDone(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal
      title={`Delete ${names?.length ?? 0} experiments?`}
      open={names !== null}
      onCancel={onCancel}
      onOk={handleDelete}
      okButtonProps={{ danger: true, disabled: confirmText !== 'DELETE', loading: deleting }}
      okText="Delete"
      destroyOnHidden
    >
      {error && (
        <Typography.Paragraph type="danger">
          {error}
        </Typography.Paragraph>
      )}
      <Typography.Paragraph type="danger">
        This will permanently delete {names?.length ?? 0} experiments including all their assignments, datasets
        and analysis results. This action cannot be undone.
      </Typography.Paragraph>
      <List
        size="small"
        bordered
        dataSource={names ?? []}
        renderItem={(name) => <List.Item>{name}</List.Item>}
        style={{ maxHeight: 200, overflow: 'auto', marginBottom: 16 }}
      />
      <Form layout="vertical">
        <Form.Item label='Type "DELETE" to confirm'>
          <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoFocus />
        </Form.Item>
      </Form>
    </Modal>
  )
}
