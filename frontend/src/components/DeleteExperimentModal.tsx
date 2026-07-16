import { useEffect, useState } from 'react'
import { Modal, Typography, Form, Input, Spin } from 'antd'
import { apiClient, errorMessage } from '../api/client'
import { StopClickPropagation } from './StopClickPropagation'

interface Props {
  name: string | null
  onCancel: () => void
  onDeleted: () => void
}

// Общая модалка удаления (FRONTEND.md §5.2, текст обновлен 6-part пакетом
// пт.6): реальные числа из GET .../deletion-summary — assignments/results
// действительно удаляются, датасеты (M) только ОТВЯЗЫВАЮТСЯ (переживают
// удаление эксперимента, CLAUDE.md "датасеты — самостоятельные сущности").
// Кнопка активна только при точном вводе "DELETE". Используется и списком
// экспериментов, и страницей теста.
export function DeleteExperimentModal({ name, onCancel, onDeleted }: Props) {
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [summary, setSummary] = useState<{ assignments: number; datasets: number; results: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!name) {
      setSummary(null)
      setConfirmText('')
      return
    }
    apiClient
      .GET('/api/v1/experiments/{name}/deletion-summary', { params: { path: { name } } })
      .then(({ data }) => setSummary(data ?? null))
  }, [name])

  const handleDelete = async () => {
    if (!name) return
    setDeleting(true)
    setError(null)
    try {
      const { error } = await apiClient.DELETE('/api/v1/experiments/{name}', {
        params: { path: { name } },
        body: { confirm: confirmText },
      })
      if (error) throw new Error(errorMessage(error))
      onDeleted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal
      title={`Delete "${name}"?`}
      open={name !== null}
      onCancel={onCancel}
      onOk={handleDelete}
      okButtonProps={{ danger: true, disabled: confirmText !== 'DELETE', loading: deleting }}
      okText="Delete"
    >
      <StopClickPropagation>
        {error && (
          <Typography.Paragraph type="danger">
            {error}
          </Typography.Paragraph>
        )}
        {summary ? (
          <Typography.Paragraph type="danger">
            You are deleting experiment {name}, including its assignments ({summary.assignments} rows) and
            analysis results ({summary.results}). Linked datasets ({summary.datasets}) will NOT be deleted — they
            remain on the Datasets page. This action cannot be undone.
          </Typography.Paragraph>
        ) : (
          <Spin size="small" />
        )}
        <Form layout="vertical">
          <Form.Item label='Type "DELETE" to confirm'>
            <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoFocus />
          </Form.Item>
        </Form>
      </StopClickPropagation>
    </Modal>
  )
}
