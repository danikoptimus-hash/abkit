import { Select, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { formatRelativeTime } from '../dateFormat'

const SOURCE_LABELS: Record<string, string> = { upload: 'Upload', sql: 'SQL', demo: 'Demo' }
const SOURCE_COLORS: Record<string, string> = { upload: 'default', sql: 'blue', demo: 'purple' }

export function SourceTag({ source }: { source: string }) {
  return <Tag color={SOURCE_COLORS[source] ?? 'default'}>{SOURCE_LABELS[source] ?? source}</Tag>
}

// Datasets page is now the only place files are uploaded or SQL datasets
// are created (DB3, CLAUDE.md dataset-centric model) — design/analyze/
// validation all pick from the same list via this component instead of
// uploading directly.
export function DatasetSelect({
  value,
  onChange,
  placeholder = 'Select a dataset',
  disabled = false,
  style,
  ariaLabel,
}: {
  value: string | undefined
  onChange: (id: string) => void
  placeholder?: string
  disabled?: boolean
  style?: React.CSSProperties
  // AntD's placeholder renders as visible text, not a real `placeholder`
  // attribute — Playwright's getByPlaceholder can't find it, so callers
  // that need a stable e2e locator pass a distinct aria-label instead
  // (page.getByRole('combobox', { name: ariaLabel })).
  ariaLabel?: string
}) {
  const { data, isFetching } = useQuery({
    queryKey: ['datasets-for-select'],
    queryFn: async () => {
      const { data } = await apiClient.GET('/api/v1/datasets', { params: { query: { page_size: 200 } } })
      return data?.items ?? []
    },
  })

  const items = data ?? []

  return (
    <Select
      showSearch
      allowClear
      loading={isFetching}
      disabled={disabled}
      placeholder={placeholder}
      style={{ width: '100%', ...style }}
      value={value}
      onChange={onChange}
      aria-label={ariaLabel}
      optionFilterProp="label"
      options={items.map((d) => ({
        value: d.id,
        label: `${d.filename} (${d.n_rows} rows)`,
        dataset: d,
      }))}
      optionRender={(option) => {
        const d = option.data.dataset as (typeof items)[number]
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SourceTag source={d.source} />
            <span>{d.filename}</span>
            <span style={{ color: 'rgba(0,0,0,0.45)', fontSize: 12 }}>
              {d.n_rows} rows &middot; {d.uploaded_at ? formatRelativeTime(d.uploaded_at) : '—'}
            </span>
          </div>
        )
      }}
    />
  )
}
