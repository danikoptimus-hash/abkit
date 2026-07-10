import { useState } from 'react'
import { Button, Alert, Table } from 'antd'
import { apiClient, errorMessage } from '../../api/client'

// Shared by the "From SQL" create form and the Edit dataset modal's "Query
// result" tab (UX package, Datasets §2.2/§3) — runs whatever SQL text is
// CURRENTLY in the editor against the connection (100 rows, not saved) so
// its result can be checked/compared before committing. Uncontrolled: owns
// its own preview state, since neither caller needs to react to it.
export function QueryResultPreview({
  connectionId,
  sql,
  buttonLabel = 'Preview',
}: {
  connectionId: string | undefined
  sql: string
  buttonLabel?: string
}) {
  const [previewing, setPreviewing] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null)

  const runPreview = async () => {
    if (!connectionId || !sql.trim()) return
    setPreviewing(true)
    setPreviewError(null)
    setPreview(null)
    try {
      const { data, error } = await apiClient.POST('/api/v1/db-connections/{conn_id}/preview', {
        params: { path: { conn_id: connectionId } },
        body: { sql },
      })
      if (error) throw new Error(errorMessage(error))
      setPreview({ columns: data.columns, rows: data.rows })
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : 'Preview failed')
    } finally {
      setPreviewing(false)
    }
  }

  return (
    <div>
      <Button onClick={runPreview} loading={previewing} disabled={!connectionId || !sql.trim()} style={{ marginBottom: 12 }}>
        {buttonLabel}
      </Button>

      {previewError && (
        <Alert type="error" message={previewError} showIcon style={{ marginBottom: 12 }} closable onClose={() => setPreviewError(null)} />
      )}

      {preview && (
        <Table
          size="small"
          dataSource={preview.rows}
          rowKey={(_, i) => String(i)}
          pagination={false}
          scroll={{ x: true, y: 240 }}
          style={{ marginBottom: 12 }}
          columns={preview.columns.map((c) => ({ title: c, dataIndex: c }))}
        />
      )}
    </div>
  )
}
