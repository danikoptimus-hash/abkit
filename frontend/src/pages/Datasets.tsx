import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Table, Drawer, Table as PreviewTable, Typography, Button, Space } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { apiClient, errorMessage } from '../api/client'
import { RelativeTime } from '../components/RelativeTime'
import { SourceTag } from '../components/DatasetSelect'
import { CreateDatasetModal } from './datasets/CreateDatasetModal'

export function DatasetsPage() {
  const [page, setPage] = useState(1)
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const pageSize = 20

  const { data, isLoading } = useQuery({
    queryKey: ['datasets', page],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/datasets', {
        params: { query: { page, page_size: pageSize } },
      })
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  const { data: preview, isFetching: previewLoading } = useQuery({
    queryKey: ['dataset-preview', previewId],
    enabled: previewId !== null,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/datasets/{dataset_id}/preview', {
        params: { path: { dataset_id: previewId! }, query: { rows: 20 } },
      })
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Datasets</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Dataset
        </Button>
      </Space>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.items ?? []}
        pagination={{ current: page, pageSize, total: data?.total ?? 0, onChange: setPage, showSizeChanger: false }}
        onRow={(record) => ({ onClick: () => setPreviewId(record.id), style: { cursor: 'pointer' } })}
        columns={[
          { title: 'File', dataIndex: 'filename' },
          { title: 'Source', dataIndex: 'source', render: (source: string) => <SourceTag source={source} /> },
          {
            title: 'Experiment',
            dataIndex: 'experiment_name',
            render: (name: string | null) => (name ? <Link to={`/experiments/${name}`}>{name}</Link> : '—'),
          },
          { title: 'Rows', dataIndex: 'n_rows' },
          { title: 'Uploaded By', dataIndex: 'uploaded_by_email' },
          { title: 'When', dataIndex: 'uploaded_at', render: (ts: string) => <RelativeTime iso={ts} /> },
        ]}
      />

      <CreateDatasetModal open={createOpen} onClose={() => setCreateOpen(false)} />

      <Drawer
        title={preview?.filename ?? 'Preview'}
        open={previewId !== null}
        onClose={() => setPreviewId(null)}
        width={720}
      >
        {preview && (
          <PreviewTable
            loading={previewLoading}
            rowKey={(_, index) => String(index)}
            dataSource={preview.rows}
            pagination={false}
            size="small"
            scroll={{ x: true }}
            columns={preview.columns.map((col) => ({ title: col, dataIndex: col }))}
          />
        )}
      </Drawer>
    </div>
  )
}
