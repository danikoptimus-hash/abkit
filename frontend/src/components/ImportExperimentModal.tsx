import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal, Typography, Upload, Alert, Button, Space } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { apiClient, errorMessage, toFormData, type ApiErrorBody } from '../api/client'
import { queryKeys } from '../api/queryKeys'

interface Props {
  open: boolean
  onClose: () => void
}

interface ImportResult {
  experiment_name: string
  original_name: string
  renamed: boolean
  warnings: string[]
}

// Импорт эксперимента из zip (пакет export/import).
//
// Три состояния, которые ТЗ требует различать, и все три — 400 от сервера, но
// с разными кодами:
//   confirmation_required     -> датасет совпал по имени, но не по содержимому:
//                                переспросить и повторить с confirm=true.
//   unsupported_format_version-> архив новее нас: тупик, только апгрейд.
//   invalid_archive           -> это не наш zip.
// Успех с непустым warnings — НЕ ошибка: тест создан, но, например, датасет не
// нашелся. Поэтому результат показываем прямо здесь (баннер), а на страницу
// теста уводим отдельной кнопкой — иначе предупреждение мелькнуло бы и ушло
// вместе с модалкой.
export function ImportExperimentModal({ open, onClose }: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nameMatches, setNameMatches] = useState<string[] | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)

  useEffect(() => {
    if (!open) return
    setFile(null)
    setImporting(false)
    setError(null)
    setNameMatches(null)
    setResult(null)
  }, [open])

  const runImport = async (confirmDatasetNames: boolean) => {
    if (!file) return
    setImporting(true)
    setError(null)
    try {
      const { data, error } = await apiClient.POST('/api/v1/experiments/import', {
        body: toFormData({
          file,
          confirm_dataset_names: String(confirmDatasetNames),
        }) as unknown as { confirm_dataset_names: boolean; file: string },
      })
      if (error) {
        const body = error as ApiErrorBody
        if (body?.error?.code === 'confirmation_required') {
          const datasets = body.error.details?.datasets
          setNameMatches(Array.isArray(datasets) ? (datasets as string[]) : [])
          return
        }
        throw new Error(errorMessage(error, 'Import failed'))
      }
      setNameMatches(null)
      setResult(data as ImportResult)
      // Новый тест обязан появиться в списке без перезагрузки; теги архива
      // могли создать новые (get-or-create) — фильтр тегов тоже устарел.
      queryClient.invalidateQueries({ queryKey: queryKeys.experimentsAll() })
      queryClient.invalidateQueries({ queryKey: queryKeys.tagsTypeaheadAll() })
      queryClient.invalidateQueries({ queryKey: queryKeys.datasetsAll() })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to import')
    } finally {
      setImporting(false)
    }
  }

  if (result) {
    return (
      <Modal
        title="Import complete"
        open={open}
        onCancel={onClose}
        footer={
          <Space>
            <Button onClick={onClose}>Close</Button>
            <Button
              type="primary"
              onClick={() => {
                onClose()
                navigate(`/experiments/${encodeURIComponent(result.experiment_name)}`)
              }}
            >
              Open test
            </Button>
          </Space>
        }
      >
        <Typography.Paragraph>
          Imported as <Typography.Text strong>{result.experiment_name}</Typography.Text> (draft,
          owned by you).
        </Typography.Paragraph>
        {result.renamed && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message={`A test named "${result.original_name}" already exists, so the imported copy was renamed.`}
          />
        )}
        {result.warnings.length > 0 && (
          <Alert
            type="warning"
            showIcon
            data-testid="import-warnings"
            message="Imported with warnings"
            description={
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            }
          />
        )}
      </Modal>
    )
  }

  return (
    <Modal
      title="Import A/B test"
      open={open}
      onCancel={onClose}
      onOk={() => runImport(false)}
      okText="Import"
      okButtonProps={{ disabled: !file || nameMatches !== null, loading: importing }}
    >
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />}
      <Typography.Paragraph>
        Upload a zip produced by Export. The test is always created as a new draft owned by you —
        nothing existing is overwritten.
      </Typography.Paragraph>
      <Upload.Dragger
        accept=".zip"
        maxCount={1}
        // Файл копим в состоянии и шлем сами (multipart с confirm-флагом), а
        // не отдаем AntD загружать — второй заход с confirm=true должен
        // отправить ТОТ ЖЕ файл, а не просить перевыбрать его.
        beforeUpload={(f) => {
          setFile(f)
          setNameMatches(null)
          setError(null)
          return false
        }}
        onRemove={() => {
          setFile(null)
          setNameMatches(null)
        }}
        fileList={file ? [{ uid: '1', name: file.name, status: 'done' }] : []}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">Click or drag an export archive here</p>
        <p className="ant-upload-hint">A .zip produced by an ABSet experiment export.</p>
      </Upload.Dragger>
      {nameMatches !== null && (
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 12 }}
          data-testid="dataset-name-match-confirm"
          message="Link datasets by name?"
          description={
            <>
              <Typography.Paragraph style={{ marginBottom: 8 }}>
                {nameMatches.join(', ')} — a dataset with this name exists here, but its contents
                differ from the exported one. Linking by name lets the test open, but analysis may
                not reproduce exactly.
              </Typography.Paragraph>
              <Button size="small" loading={importing} onClick={() => runImport(true)}>
                Link by name and import
              </Button>
            </>
          }
        />
      )}
    </Modal>
  )
}
