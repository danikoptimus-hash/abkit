import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Table, Input, Select, Button, Tag, Space, Modal, Form, message, Typography } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { apiClient, errorMessage } from '../api/client'
import { useAuth, hasMinRole } from '../auth/AuthContext'

const STATUS_COLORS: Record<string, string> = {
  designed: 'default',
  running: 'success',
  completed: 'blue',
  archived: 'default',
}

function StatusBadge({ status }: { status: string }) {
  return <Tag color={STATUS_COLORS[status] ?? 'default'}>{status}</Tag>
}

function PublicationBadge({ status }: { status: string }) {
  return <Tag color={status === 'published' ? 'success' : 'default'}>{status === 'published' ? 'published' : 'draft'}</Tag>
}

export function ExperimentsListPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data, isLoading } = useQuery({
    queryKey: ['experiments', { q, status, page }],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/experiments', {
        params: { query: { q: q || undefined, status, page, page_size: pageSize } },
      })
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)

  const canCreate = hasMinRole(user, 'editor')

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const { error } = await apiClient.DELETE('/api/v1/experiments/{name}', {
        params: { path: { name: deleteTarget } },
        body: { confirm: confirmText },
      })
      if (error) throw new Error(errorMessage(error))
      message.success(`Эксперимент «${deleteTarget}» удален`)
      setDeleteTarget(null)
      setConfirmText('')
      queryClient.invalidateQueries({ queryKey: ['experiments'] })
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Не удалось удалить')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Input.Search
            placeholder="Поиск по названию"
            allowClear
            style={{ width: 260 }}
            onSearch={(value) => {
              setQ(value)
              setPage(1)
            }}
          />
          <Select
            placeholder="Статус"
            allowClear
            style={{ width: 160 }}
            options={[
              { value: 'designed', label: 'designed' },
              { value: 'running', label: 'running' },
              { value: 'completed', label: 'completed' },
              { value: 'archived', label: 'archived' },
            ]}
            onChange={(value) => {
              setStatus(value)
              setPage(1)
            }}
          />
        </Space>
        {canCreate && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/experiments/new')}>
            Создать A/B тест
          </Button>
        )}
      </Space>

      <Table
        rowKey="name"
        loading={isLoading}
        dataSource={data?.items ?? []}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
          onChange: setPage,
          showSizeChanger: false,
        }}
        columns={[
          {
            title: 'Название',
            dataIndex: 'name',
            render: (name: string) => <Link to={`/experiments/${name}`}>{name}</Link>,
          },
          { title: 'Владелец', dataIndex: 'owner_email' },
          { title: 'Статус', dataIndex: 'status', render: (s: string) => <StatusBadge status={s} /> },
          {
            title: 'Публикация',
            dataIndex: 'publication_status',
            render: (s: string) => <PublicationBadge status={s} />,
          },
          {
            title: 'Изменен',
            key: 'updated',
            render: (_, record) =>
              record.archived_at ?? record.completed_at ?? record.started_at ?? record.created_at,
          },
          {
            title: 'Действия',
            key: 'actions',
            render: (_, record) => (
              <Button
                danger
                size="small"
                disabled={!hasMinRole(user, 'editor')}
                onClick={() => setDeleteTarget(record.name)}
              >
                Удалить
              </Button>
            ),
          },
        ]}
      />

      <Modal
        title={`Удалить «${deleteTarget}»?`}
        open={deleteTarget !== null}
        onCancel={() => {
          setDeleteTarget(null)
          setConfirmText('')
        }}
        onOk={handleDelete}
        okButtonProps={{ danger: true, disabled: confirmText !== 'DELETE', loading: deleting }}
        okText="Удалить"
      >
        <Typography.Paragraph type="danger">
          Это действие необратимо: будут удалены назначения, датасеты и результаты анализа этого
          эксперимента.
        </Typography.Paragraph>
        <Form layout="vertical">
          <Form.Item label='Введите "DELETE" для подтверждения'>
            <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoFocus />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
