import { useEffect, useRef } from 'react'
import { Typography, Select, Button, Space, Tooltip } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { apiClient, errorMessage } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'

// Shared by the "From SQL" create form and the Edit dataset modal (UX
// package, Datasets §3 — "сегодняшний баг — ровно следствие дублирования"):
// two optional, cascading, typeahead selects backed by the schema/table
// introspection endpoints (60s server-side cache, 🗘 bypasses it). Fully
// controlled — schema/table state and what happens to the SQL box when a
// table is picked both live in the parent, since that decision differs
// between create (silently fill if unedited) and edit (confirm if the
// existing query looks hand-written).
export function SchemaTableCascade({
  connectionId,
  schema,
  table,
  onSchemaChange,
  onTableChange,
}: {
  connectionId: string | undefined
  schema: string | undefined
  table: string | undefined
  onSchemaChange: (schema: string | undefined) => void
  onTableChange: (table: string | undefined) => void
}) {
  const forceRefreshSchemas = useRef(false)
  const forceRefreshTables = useRef(false)
  // Reset schema/table when the connection actually CHANGES (not on mount,
  // where connectionId may already be prefilled — e.g. Edit opening on an
  // existing source=sql dataset) — a different connection has a different
  // schema/table namespace entirely.
  const mountedConnectionId = useRef(connectionId)

  useEffect(() => {
    if (mountedConnectionId.current !== connectionId) {
      mountedConnectionId.current = connectionId
      onSchemaChange(undefined)
      onTableChange(undefined)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId])

  const {
    data: schemas, isFetching: schemasLoading, refetch: refetchSchemas,
  } = useQuery({
    queryKey: queryKeys.dbConnectionSchemas(connectionId),
    enabled: !!connectionId,
    queryFn: async () => {
      const refresh = forceRefreshSchemas.current
      forceRefreshSchemas.current = false
      const { data, error } = await apiClient.GET('/api/v1/db-connections/{conn_id}/schemas', {
        params: { path: { conn_id: connectionId! }, query: { refresh } },
      })
      if (error) throw new Error(errorMessage(error))
      return data.schemas
    },
  })

  const {
    data: tables, isFetching: tablesLoading, refetch: refetchTables,
  } = useQuery({
    queryKey: queryKeys.dbConnectionTables(connectionId, schema),
    enabled: !!connectionId && !!schema,
    queryFn: async () => {
      const refresh = forceRefreshTables.current
      forceRefreshTables.current = false
      const { data, error } = await apiClient.GET('/api/v1/db-connections/{conn_id}/schemas/{schema}/tables', {
        params: { path: { conn_id: connectionId!, schema: schema! }, query: { refresh } },
      })
      if (error) throw new Error(errorMessage(error))
      return data.tables
    },
  })

  return (
    <>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
        Schema &amp; table{' '}
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          (optional — fills in the SQL box below)
        </Typography.Text>
      </Typography.Text>
      <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
        <Select
          style={{ width: '45%' }}
          aria-label="from-sql-schema-select"
          showSearch
          allowClear
          disabled={!connectionId}
          loading={schemasLoading}
          placeholder="Schema"
          value={schema}
          onChange={(value: string | undefined) => {
            onSchemaChange(value)
            onTableChange(undefined)
          }}
          options={(schemas ?? []).map((s) => ({ value: s, label: s }))}
        />
        <Select
          style={{ width: '45%' }}
          aria-label="from-sql-table-select"
          showSearch
          allowClear
          disabled={!schema}
          loading={tablesLoading}
          placeholder="Table"
          value={table}
          onChange={onTableChange}
          options={(tables ?? []).map((t) => ({ value: t, label: t }))}
        />
        <Tooltip title="Refresh schema/table list">
          <Button
            style={{ width: '10%' }}
            icon={<ReloadOutlined />}
            disabled={!connectionId}
            onClick={() => {
              if (schema) {
                forceRefreshTables.current = true
                refetchTables()
              } else {
                forceRefreshSchemas.current = true
                refetchSchemas()
              }
            }}
          />
        </Tooltip>
      </Space.Compact>
    </>
  )
}
