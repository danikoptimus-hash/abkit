import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { Typography, Tag, Descriptions, Select, message, Spin, Result } from 'antd'
import { apiClient, errorMessage } from '../api/client'
import { useAuth, hasMinRole } from '../auth/AuthContext'

// Заглушка (FRONTEND.md §7 R4): читает уже готовый GET /experiments/{name}
// (R2) и позволяет менять операционный статус (R3), но НЕ содержит шапки с
// markdown-блоками/режима Edit/секций Дизайн-Анализ-История — та полная
// страница теста строится в R5/R6.
export function ExperimentDetailStubPage() {
  const { name } = useParams<{ name: string }>()
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['experiment', name],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/experiments/{name}', {
        params: { path: { name: name! } },
      })
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  const handleStatusChange = async (to: string) => {
    const { error } = await apiClient.POST('/api/v1/experiments/{name}/status', {
      params: { path: { name: name! } },
      body: { to },
    })
    if (error) {
      message.error(errorMessage(error))
      return
    }
    queryClient.invalidateQueries({ queryKey: ['experiment', name] })
    queryClient.invalidateQueries({ queryKey: ['experiments'] })
  }

  if (isLoading) return <Spin size="large" />
  if (error || !data) {
    return <Result status="404" title="Эксперимент не найден" />
  }

  const canEdit = hasMinRole(user, 'editor')

  return (
    <div>
      <Typography.Title level={4}>
        {data.name} <Tag color={data.publication_status === 'published' ? 'success' : 'default'}>{data.publication_status}</Tag>
      </Typography.Title>
      <Descriptions bordered column={2} size="small" style={{ marginBottom: 24 }}>
        <Descriptions.Item label="Владелец">{data.owner_email}</Descriptions.Item>
        <Descriptions.Item label="Статус">
          <Select
            value={data.status}
            disabled={!canEdit}
            style={{ width: 160 }}
            onChange={handleStatusChange}
            options={['designed', 'running', 'completed', 'archived'].map((s) => ({ value: s, label: s }))}
          />
        </Descriptions.Item>
        <Descriptions.Item label="Создан">{data.created_at}</Descriptions.Item>
        <Descriptions.Item label="Отчеты">{data.available_reports.join(', ') || '—'}</Descriptions.Item>
      </Descriptions>
      <Typography.Title level={5}>Конфигурация</Typography.Title>
      <pre style={{ background: '#F7F7F7', padding: 16, borderRadius: 4, overflow: 'auto' }}>
        {JSON.stringify(data.config, null, 2)}
      </pre>
    </div>
  )
}
