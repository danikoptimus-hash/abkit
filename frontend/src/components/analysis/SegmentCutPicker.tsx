import { useMemo, useState } from 'react'
import { Select, Button, Tag, Space, Typography, Alert } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { apiClient, errorMessage } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import { combinationCellCount, segmentCardinalityStatus } from '../../pages/experiment/segmentGuard'

export interface SegmentCuts {
  columns: string[]
  combinations: string[][]
}

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.includes(x))

export function comboLabel(cols: string[]): string {
  return cols.join(' × ')
}

// Shared picker for segment cuts — single columns AND cross-column
// combinations — with the live cardinality guard. Used both to declare cuts
// before running (AnalyzeSection) and to add a cut post-hoc (ResultsSection).
export function SegmentCutPicker({
  datasetId,
  columns,
  value,
  onChange,
  disabled,
}: {
  datasetId: string
  columns: string[]
  value: SegmentCuts
  onChange: (next: SegmentCuts) => void
  disabled?: boolean
}) {
  const [comboCols, setComboCols] = useState<string[]>([])

  // Effective (post-bucketing) distinct counts per column, for the product
  // cell-count guard. One fetch per dataset (reads the file server-side).
  const { data: cardData } = useQuery({
    queryKey: queryKeys.datasetColumnCardinalities(datasetId, columns),
    enabled: !!datasetId && columns.length > 0,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/datasets/{dataset_id}/column-cardinalities', {
        params: { path: { dataset_id: datasetId }, query: { columns } },
      })
      if (error) throw new Error(errorMessage(error))
      return data.cardinalities
    },
  })
  const cardinalities = cardData ?? {}

  const comboCells = useMemo(() => combinationCellCount(comboCols, cardinalities), [comboCols, cardinalities])
  const comboStatus = segmentCardinalityStatus(comboCells)
  const isDuplicate =
    comboCols.length >= 2 && value.combinations.some((c) => sameSet(c, comboCols))
  const canAdd = comboCols.length >= 2 && comboStatus !== 'refuse' && !isDuplicate

  const addCombination = () => {
    if (!canAdd) return
    onChange({ ...value, combinations: [...value.combinations, comboCols] })
    setComboCols([])
  }
  const removeCombination = (idx: number) =>
    onChange({ ...value, combinations: value.combinations.filter((_, i) => i !== idx) })

  const options = columns.map((c) => ({ value: c, label: c }))

  return (
    <div>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
        Single columns
      </Typography.Text>
      <Select
        mode="multiple"
        style={{ width: '100%' }}
        placeholder="Break the effect down by these columns"
        value={value.columns}
        onChange={(cols) => onChange({ ...value, columns: cols })}
        options={options}
        disabled={disabled}
        aria-label="segment-columns-select"
      />

      <Typography.Text type="secondary" style={{ display: 'block', margin: '12px 0 4px', fontSize: 13 }}>
        Combinations (cross 2+ columns)
      </Typography.Text>
      {value.combinations.length > 0 && (
        <Space wrap style={{ marginBottom: 8 }}>
          {value.combinations.map((cols, idx) => (
            <Tag
              key={comboLabel(cols)}
              closable={!disabled}
              onClose={() => removeCombination(idx)}
              color="geekblue"
            >
              {comboLabel(cols)} ({combinationCellCount(cols, cardinalities)} cells)
            </Tag>
          ))}
        </Space>
      )}
      <Space.Compact style={{ width: '100%' }}>
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="Pick 2+ columns to cross"
          value={comboCols}
          onChange={setComboCols}
          options={options}
          disabled={disabled}
          aria-label="segment-combination-select"
        />
        <Button icon={<PlusOutlined />} onClick={addCombination} disabled={disabled || !canAdd}>
          Add
        </Button>
      </Space.Compact>
      {comboCols.length >= 2 && (
        <Typography.Paragraph
          type={comboStatus === 'refuse' ? 'danger' : comboStatus === 'warn' ? 'warning' : 'secondary'}
          style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}
        >
          {comboLabel(comboCols)} → {comboCells} cells
          {isDuplicate && ' — already added'}
          {!isDuplicate && comboStatus === 'refuse' &&
            ' — this many segments is noise, not analysis. Narrow the combination.'}
          {!isDuplicate && comboStatus === 'warn' && ' — a lot of segments; many will be underpowered.'}
        </Typography.Paragraph>
      )}
      {comboStatus === 'refuse' && !isDuplicate && comboCols.length >= 2 && (
        <Alert
          type="error"
          showIcon
          style={{ marginTop: 8 }}
          message="Too many segments to add (> 200 cells)."
        />
      )}
    </div>
  )
}
