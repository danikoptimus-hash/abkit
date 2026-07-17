import { useEffect, useState } from 'react'
import { Modal, Typography, Checkbox, Alert } from 'antd'
import { errorMessage } from '../api/client'
import { StopClickPropagation } from './StopClickPropagation'

interface Props {
  name: string | null
  onCancel: () => void
}

// Экспорт эксперимента в zip (пакет export/import). Модалка нужна только
// ради галочки "Include dataset snapshots" — без нее это была бы просто
// ссылка.
//
// Скачивание — через fetch+blob, а не <Button href>, как у отчетов/samples:
// экспорт умеет отказать (403 для viewer, 404 на невидимом черновике), а у
// href-навигации отказ выглядит как "ничего не произошло" — тут же ошибку
// показываем текстом в самой модалке.
export function ExportExperimentModal({ name, onCancel }: Props) {
  const [includeDatasets, setIncludeDatasets] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (name === null) return
    setIncludeDatasets(false)
    setError(null)
  }, [name])

  const handleExport = async () => {
    if (!name) return
    setExporting(true)
    setError(null)
    try {
      const url =
        `/api/v1/experiments/${encodeURIComponent(name)}/export` +
        `?include_datasets=${includeDatasets}`
      const response = await fetch(url, { credentials: 'include' })
      if (!response.ok) {
        // Тело ошибки — обычный конверт {error:{code,message}}; на совсем
        // неожиданном ответе (например, прокси вернул HTML) не падаем в
        // разборе, а показываем статус.
        let body: unknown = null
        try {
          body = await response.json()
        } catch {
          body = null
        }
        throw new Error(
          body ? errorMessage(body, `Export failed (${response.status})`) : `Export failed (${response.status})`,
        )
      }
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      // Имя задаем сами, а не парсим RFC 5987 filename* из
      // Content-Disposition: сервер строит его по тому же правилу, а разбор
      // заголовка на клиенте — лишний способ ошибиться.
      link.download = `${name}_export.zip`
      link.click()
      URL.revokeObjectURL(objectUrl)
      onCancel()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to export')
    } finally {
      setExporting(false)
    }
  }

  return (
    <Modal
      title={`Export "${name}"`}
      open={name !== null}
      onCancel={onCancel}
      onOk={handleExport}
      okText="Export"
      okButtonProps={{ loading: exporting }}
    >
      <StopClickPropagation>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />}
        <Typography.Paragraph>
          Downloads a zip archive with this test's design, assignments, analysis results and
          reports. You can import it into another ABSet instance, or back into this one.
        </Typography.Paragraph>
        <Checkbox
          checked={includeDatasets}
          onChange={(e) => setIncludeDatasets(e.target.checked)}
          data-testid="include-dataset-snapshots"
        >
          Include dataset snapshots
        </Checkbox>
        <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
          Off by default: datasets are referenced by name and content hash, which is enough when
          the target instance already has the same data. Turn it on to carry the data itself — a
          much larger file, needed when migrating to an instance that doesn't have these datasets.
        </Typography.Paragraph>
      </StopClickPropagation>
    </Modal>
  )
}
