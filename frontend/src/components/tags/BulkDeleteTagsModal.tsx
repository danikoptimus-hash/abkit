import { useEffect, useState } from 'react'
import { Modal, Typography, Form, Input, List, Alert } from 'antd'
import { apiClient, errorMessage } from '../../api/client'
import type { components } from '../../api/schema'

type TagAdminOut = components['schemas']['TagAdminOut']

export interface BulkDeleteTagsResult {
  deleted: string[]
  skipped: { tag_id: string; reason: string }[]
}

interface Props {
  tags: TagAdminOut[] | null
  onCancel: () => void
  onDone: (result: BulkDeleteTagsResult) => void
}

// Mirrors components/datasets/BulkDeleteDatasetsModal.tsx — one typed-DELETE
// confirmation for the whole batch (tag management page §2.4). Unlike the
// dataset version, no separate usage fetch is needed: the admin tags list
// (GET /tags/admin) already carries each row's experiment_count.
export function BulkDeleteTagsModal({ tags, onCancel, onDone }: Props) {
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setConfirmText('')
    setError(null)
  }, [tags])

  const usedCount = (tags ?? []).filter((t) => t.experiment_count > 0).length

  const handleDelete = async () => {
    if (!tags) return
    setDeleting(true)
    setError(null)
    try {
      const { data, error } = await apiClient.POST('/api/v1/tags/bulk-delete', {
        body: { tag_ids: tags.map((t) => t.id), confirm: confirmText },
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
      title={`Delete ${tags?.length ?? 0} tags?`}
      open={tags !== null}
      onCancel={onCancel}
      onOk={handleDelete}
      okButtonProps={{ danger: true, disabled: confirmText !== 'DELETE', loading: deleting }}
      okText="Delete"
      destroyOnHidden
    >
      {error && <Typography.Paragraph type="danger">{error}</Typography.Paragraph>}
      <Typography.Paragraph type="danger">
        This will permanently delete {tags?.length ?? 0} tags. This action cannot be undone.
        {usedCount > 0 && (
          <>
            {' '}
            {usedCount} of them {usedCount === 1 ? 'is' : 'are'} used by experiments — they will be removed from
            those experiments.
          </>
        )}
      </Typography.Paragraph>
      <List
        size="small"
        bordered
        dataSource={tags ?? []}
        renderItem={(t) => (
          <List.Item>
            <div>
              <div>{t.name}</div>
              {t.experiment_count > 0 && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  used by {t.experiment_count} experiment{t.experiment_count === 1 ? '' : 's'}
                </Typography.Text>
              )}
            </div>
          </List.Item>
        )}
        style={{ maxHeight: 240, overflow: 'auto', marginBottom: 16 }}
      />
      {usedCount > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`${usedCount} tag${usedCount === 1 ? '' : 's'} in use — deleting anyway is allowed but not reversible.`}
        />
      )}
      <Form layout="vertical">
        <Form.Item label='Type "DELETE" to confirm'>
          <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoFocus />
        </Form.Item>
      </Form>
    </Modal>
  )
}
