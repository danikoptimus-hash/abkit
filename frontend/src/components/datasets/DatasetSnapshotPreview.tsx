import { Typography, Table } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { apiClient, errorMessage } from '../../api/client'
import { RelativeTime } from '../RelativeTime'

// Edit dataset modal (UX package, Datasets §2.1/§2.3) — the first 10 rows of
// the dataset's CURRENTLY STORED snapshot (not a live re-query), same
// endpoint the Datasets list's preview drawer already uses — same query key
// too, so a Refresh elsewhere in the app invalidates this for free.
export function DatasetSnapshotPreview({
  datasetId,
  nRows,
  fetchedAt,
}: {
  datasetId: string
  nRows: number
  fetchedAt: string | null
}) {
  const { data: preview, isFetching } = useQuery({
    queryKey: ['dataset-preview', datasetId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/datasets/{dataset_id}/preview', {
        params: { path: { dataset_id: datasetId }, query: { rows: 10 } },
      })
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  return (
    <div>
      <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
        Stored snapshot: {nRows} rows, fetched <RelativeTime iso={fetchedAt} />
      </Typography.Text>
      {preview && (
        <Table
          size="small"
          loading={isFetching}
          dataSource={preview.rows}
          rowKey={(_, i) => String(i)}
          pagination={false}
          scroll={{ x: true, y: 240 }}
          columns={preview.columns.map((c) => ({ title: c, dataIndex: c }))}
        />
      )}
    </div>
  )
}
