import { useState } from 'react'
import { Upload, Button, Select, Checkbox, Typography, Alert, Progress, Tooltip } from 'antd'
import { InboxOutlined, ThunderboltOutlined, ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { UploadProps } from 'antd'
import { apiClient, errorMessage, toFormData } from '../../api/client'
import { useJobPolling } from '../../api/useJobPolling'
import { AnalyzeResults } from './AnalyzeResults'
import { experimentResultsQueryKey, fetchExperimentResults } from './resultsQuery'

const { Dragger } = Upload

const CORRECTION_OPTIONS = [
  { value: 'holm', label: 'holm' },
  { value: 'bonferroni', label: 'bonferroni' },
  { value: 'fdr_bh', label: 'fdr_bh (Benjamini-Hochberg)' },
  { value: 'none', label: 'no correction' },
]

interface PreparedDataset {
  id: string
  filename: string
  nRows: number
  columns: string[]
  isDemo: boolean
}

export function AnalyzeSection({ experimentName, hasAssignments }: { experimentName: string; hasAssignments: boolean }) {
  const queryClient = useQueryClient()
  const [prepared, setPrepared] = useState<PreparedDataset | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [correction, setCorrection] = useState('holm')
  const [compareMethods, setCompareMethods] = useState(false)
  const [dateCol, setDateCol] = useState<string | undefined>(undefined)

  // null = follow the default (open until the first result exists, then
  // collapsed behind "Re-run analysis" — UX package, п.3).
  const [panelOverride, setPanelOverride] = useState<boolean | null>(null)

  const { phase, stage, error, poll, reset } = useJobPolling<{ experiment_name: string }>()

  // Same query key as ResultsSection (Results tab) — shares one cache entry,
  // so whichever tab mounts first fetches and invalidateQueries below
  // refreshes both at once (including one that isn't currently mounted).
  const { data: results } = useQuery({
    queryKey: experimentResultsQueryKey(experimentName),
    queryFn: () => fetchExperimentResults(experimentName),
  })

  const panelOpen = panelOverride ?? !results
  const running = phase === 'running'

  const openRerunPanel = () => {
    setPrepared(null)
    setDateCol(undefined)
    reset()
    setPanelOverride(true)
  }

  const uploadProps: UploadProps = {
    accept: '.csv',
    multiple: false,
    showUploadList: false,
    disabled: uploading || running,
    customRequest: async (options) => {
      const file = options.file as File
      setUploading(true)
      setUploadError(null)
      try {
        const { data, error } = await apiClient.POST('/api/v1/datasets', {
          body: toFormData({ kind: 'post_analysis', experiment_name: experimentName, file }) as unknown as {
            kind: string
            file: string
          },
        })
        if (error) throw new Error(errorMessage(error))
        setPrepared({ id: data.id, filename: data.filename, nRows: data.n_rows, columns: data.columns, isDemo: false })
        options.onSuccess?.(data)
      } catch (e) {
        setUploadError(e instanceof Error ? e.message : 'Failed to upload file')
        options.onError?.(e as Error)
      } finally {
        setUploading(false)
      }
    },
  }

  const generateDemoData = async () => {
    setUploading(true)
    setUploadError(null)
    try {
      const { data, error } = await apiClient.POST('/api/v1/experiments/{name}/demo-post-data', {
        params: { path: { name: experimentName } },
        body: { effect: 0.03 },
      })
      if (error) throw new Error(errorMessage(error))
      setPrepared({ id: data.id, filename: data.filename, nRows: data.n_rows, columns: data.columns, isDemo: true })
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Failed to generate demo data')
    } finally {
      setUploading(false)
    }
  }

  const runAnalyze = async () => {
    if (!prepared) return
    reset()
    const { data, error } = await apiClient.POST('/api/v1/experiments/{name}/analyze', {
      params: { path: { name: experimentName } },
      body: { dataset_id: prepared.id, correction, compare_methods: compareMethods, date_col: dateCol ?? null },
    })
    if (error) {
      setUploadError(errorMessage(error))
      return
    }
    await poll(data.job_id)
    await queryClient.invalidateQueries({ queryKey: experimentResultsQueryKey(experimentName) })
    setPanelOverride(false)
  }

  return (
    <div>
      {uploadError && <Alert type="error" showIcon message={uploadError} style={{ marginBottom: 16, maxWidth: 480 }} closable onClose={() => setUploadError(null)} />}

      {panelOpen && (
        <div style={{ maxWidth: 480 }}>
          {/* Analysis options — read at the moment "Run analysis" is
              clicked, so they need to be set BEFORE data is uploaded/run,
              not after (UX package, item A). */}
          <Typography.Text strong>Analysis options</Typography.Text>
          <div style={{ marginTop: 8, marginBottom: 24 }}>
            <div style={{ marginBottom: 12 }}>
              <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                Multiple testing correction
              </Typography.Text>
              <Select
                style={{ width: '100%' }}
                value={correction}
                onChange={setCorrection}
                options={CORRECTION_OPTIONS}
                disabled={running}
              />
            </div>
            <Checkbox checked={compareMethods} onChange={(e) => setCompareMethods(e.target.checked)} disabled={running}>
              Compare alternative methods
            </Checkbox>
            {prepared && prepared.columns.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                  Date column (optional)
                </Typography.Text>
                <Select
                  style={{ width: '100%' }}
                  placeholder="For cumulative lift, if the data has multiple rows per user"
                  allowClear
                  value={dateCol}
                  onChange={setDateCol}
                  options={prepared.columns.map((c) => ({ value: c, label: c }))}
                  disabled={running}
                />
              </div>
            )}
          </div>

          <Typography.Text strong>Data</Typography.Text>
          <div style={{ marginTop: 8, marginBottom: 16 }}>
            <Dragger {...uploadProps} style={{ marginBottom: 12 }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p>Upload post-period data (CSV)</p>
            </Dragger>
            <Tooltip title={hasAssignments ? '' : 'No assignments for this experiment'}>
              <Button
                icon={<ThunderboltOutlined />}
                disabled={!hasAssignments || uploading || running}
                loading={uploading}
                onClick={generateDemoData}
                block
              >
                Generate demo post-period data (+3% effect)
              </Button>
            </Tooltip>

            {prepared && (
              <Alert
                type="success"
                showIcon
                icon={<CheckCircleOutlined />}
                style={{ marginTop: 12 }}
                message={
                  prepared.isDemo
                    ? `Demo data generated: ${prepared.nRows} users, +3% injected effect`
                    : `Data ready: ${prepared.filename} — ${prepared.nRows} rows, ${prepared.columns.length} columns`
                }
              />
            )}
          </div>

          <Tooltip title={prepared ? '' : 'Upload post-period data or generate demo data first'}>
            <Button
              type="primary"
              onClick={runAnalyze}
              disabled={!prepared || running}
              loading={running}
              style={{ marginBottom: 24 }}
            >
              {running ? 'Running analysis...' : 'Run analysis'}
            </Button>
          </Tooltip>
        </div>
      )}

      {phase === 'running' && (
        <div style={{ marginBottom: 24, maxWidth: 480 }}>
          <Progress percent={undefined} status="active" showInfo={false} />
          <Typography.Text>{stage ?? 'Starting analysis...'}</Typography.Text>
        </div>
      )}

      {phase === 'failed' && error && (
        <Alert type="error" showIcon message={error} style={{ marginBottom: 24, maxWidth: 480 }} />
      )}

      {results && !panelOpen && (
        <Button icon={<ReloadOutlined />} onClick={openRerunPanel} style={{ marginBottom: 16 }}>
          Re-run analysis
        </Button>
      )}

      {results && <AnalyzeResults data={results} />}
    </div>
  )
}
