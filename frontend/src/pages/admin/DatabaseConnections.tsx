import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Table, Button, Modal, Form, Input, Select, Switch, InputNumber, message, Typography, Space, Alert,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { apiClient, errorMessage } from '../../api/client'
import { RelativeTime } from '../../components/RelativeTime'
import type { components } from '../../api/schema'

type DatabaseConnectionOut = components['schemas']['DatabaseConnectionOut']
type Engine = 'postgresql' | 'clickhouse' | 'mssql'

// Mirrors abkit/db_connections/engines.py::_DEFAULT_PORTS — ClickHouse uses
// clickhouse-connect's HTTP(S) protocol, not the native TCP ports
// (9000/9440), so the defaults here are 8123/8443.
const DEFAULT_PORTS: Record<Engine, { plain: number; ssl: number }> = {
  postgresql: { plain: 5432, ssl: 5432 },
  clickhouse: { plain: 8123, ssl: 8443 },
  mssql: { plain: 1433, ssl: 1433 },
}

const ENGINE_OPTIONS = [
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'clickhouse', label: 'ClickHouse' },
  { value: 'mssql', label: 'Microsoft SQL Server' },
]

interface ConnectionFormValues {
  display_name: string
  engine: Engine
  host: string
  port: number
  database: string
  username: string
  password?: string
  extra_params?: string
  ssl: boolean
}

function TestConnectionButton({ getValues }: { getValues: () => Partial<ConnectionFormValues> | null }) {
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  const run = async () => {
    const values = getValues()
    if (!values?.host || !values.database || !values.username) {
      setResult({ ok: false, message: 'Fill in host, database, and username first' })
      return
    }
    setTesting(true)
    setResult(null)
    try {
      let extraParams: Record<string, unknown> | null = null
      if (values.extra_params?.trim()) {
        extraParams = JSON.parse(values.extra_params)
      }
      const { data, error } = await apiClient.POST('/api/v1/admin/db-connections/test-draft', {
        body: {
          engine: values.engine!, host: values.host, port: values.port!, database: values.database,
          username: values.username, password: values.password ?? '', ssl: values.ssl ?? false,
          extra_params: extraParams,
        },
      })
      if (error) throw new Error(errorMessage(error))
      setResult({ ok: data.outcome === 'ok', message: data.message })
    } catch (e) {
      setResult({ ok: false, message: e instanceof Error ? e.message : 'Test failed' })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <Button onClick={run} loading={testing}>
        Test connection
      </Button>
      {result && (
        <Alert
          type={result.ok ? 'success' : 'error'}
          showIcon
          message={result.message}
          style={{ marginTop: 8 }}
        />
      )}
    </div>
  )
}

export function DatabaseConnectionsPage() {
  const queryClient = useQueryClient()
  const [modalConn, setModalConn] = useState<DatabaseConnectionOut | 'new' | null>(null)
  const [form] = Form.useForm<ConnectionFormValues>()
  const [saving, setSaving] = useState(false)

  const { data: connections, isLoading } = useQuery({
    queryKey: ['admin-db-connections'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/admin/db-connections')
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  const applyDefaultPort = (engine: Engine, ssl?: boolean) => {
    const useSsl = ssl ?? form.getFieldValue('ssl') ?? false
    form.setFieldsValue({ port: DEFAULT_PORTS[engine][useSsl ? 'ssl' : 'plain'] })
  }

  const openEdit = (conn: DatabaseConnectionOut) => {
    setModalConn(conn)
    form.setFieldsValue({
      display_name: conn.display_name, engine: conn.engine as Engine, host: conn.host, port: conn.port,
      database: conn.database, username: conn.username, password: undefined,
      extra_params: conn.extra_params ? JSON.stringify(conn.extra_params, null, 2) : '',
      ssl: conn.ssl,
    })
  }

  const openCreate = () => {
    setModalConn('new')
    form.resetFields()
    form.setFieldsValue({ engine: 'postgresql', port: DEFAULT_PORTS.postgresql.plain, ssl: false })
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      let extraParams: Record<string, unknown> | null = null
      if (values.extra_params?.trim()) {
        try {
          extraParams = JSON.parse(values.extra_params)
        } catch {
          throw new Error('Additional Parameters must be valid JSON')
        }
      }
      if (modalConn === 'new') {
        if (!values.password) throw new Error('Password is required for a new connection')
        const { error } = await apiClient.POST('/api/v1/admin/db-connections', {
          body: {
            display_name: values.display_name, engine: values.engine, host: values.host, port: values.port,
            database: values.database, username: values.username, password: values.password,
            extra_params: extraParams, ssl: values.ssl,
          },
        })
        if (error) throw new Error(errorMessage(error))
      } else if (modalConn) {
        const { error } = await apiClient.PATCH('/api/v1/admin/db-connections/{conn_id}', {
          params: { path: { conn_id: modalConn.id } },
          body: {
            display_name: values.display_name, engine: values.engine, host: values.host, port: values.port,
            database: values.database, username: values.username,
            password: values.password || undefined, extra_params: extraParams, ssl: values.ssl,
          },
        })
        if (error) throw new Error(errorMessage(error))
      }
      message.success('Saved')
      setModalConn(null)
      queryClient.invalidateQueries({ queryKey: ['admin-db-connections'] })
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleTestSaved = async (conn: DatabaseConnectionOut) => {
    const { data, error } = await apiClient.POST('/api/v1/admin/db-connections/{conn_id}/test', {
      params: { path: { conn_id: conn.id } },
    })
    if (error) {
      message.error(errorMessage(error))
      return
    }
    if (data.outcome === 'ok') {
      message.success(data.message)
    } else {
      message.error(data.message)
    }
  }

  const handleDelete = (conn: DatabaseConnectionOut) => {
    Modal.confirm({
      title: `Delete "${conn.display_name}"?`,
      content: 'Datasets created from this connection keep their data but can no longer be refreshed.',
      okText: 'Delete',
      okButtonProps: { danger: true },
      onOk: async () => {
        const { error } = await apiClient.DELETE('/api/v1/admin/db-connections/{conn_id}', {
          params: { path: { conn_id: conn.id } },
        })
        if (error) {
          message.error(errorMessage(error))
          return
        }
        message.success('Deleted')
        queryClient.invalidateQueries({ queryKey: ['admin-db-connections'] })
      },
    })
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Database Connections
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Database
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={connections ?? []}
        columns={[
          { title: 'Name', dataIndex: 'display_name' },
          {
            title: 'Backend', dataIndex: 'engine',
            render: (engine: string) => ENGINE_OPTIONS.find((o) => o.value === engine)?.label ?? engine,
          },
          { title: 'Host', dataIndex: 'host' },
          {
            title: 'Last modified', dataIndex: 'updated_at',
            render: (ts: string) => <RelativeTime iso={ts} />,
          },
          {
            title: 'Actions',
            key: 'actions',
            render: (_, record: DatabaseConnectionOut) => (
              <Space>
                <Button size="small" onClick={() => openEdit(record)}>
                  Edit
                </Button>
                <Button size="small" onClick={() => handleTestSaved(record)}>
                  Test
                </Button>
                <Button size="small" danger onClick={() => handleDelete(record)}>
                  Delete
                </Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={modalConn === 'new' ? 'New Database Connection' : `Edit ${(modalConn as DatabaseConnectionOut)?.display_name ?? ''}`}
        open={modalConn !== null}
        onCancel={() => setModalConn(null)}
        onOk={handleSave}
        confirmLoading={saving}
        width={560}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="engine" label="Engine" rules={[{ required: true }]}>
            <Select options={ENGINE_OPTIONS} onChange={(engine: Engine) => applyDefaultPort(engine)} />
          </Form.Item>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item name="host" label="Host" rules={[{ required: true }]} style={{ width: '70%' }}>
              <Input placeholder="db.internal" />
            </Form.Item>
            <Form.Item name="port" label="Port" rules={[{ required: true }]} style={{ width: '30%' }}>
              <InputNumber style={{ width: '100%' }} min={1} max={65535} />
            </Form.Item>
          </Space.Compact>
          <Form.Item name="database" label="Database Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="username" label="Username" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label="Password"
            rules={modalConn === 'new' ? [{ required: true }] : []}
            extra={modalConn === 'new' ? undefined : 'Leave blank to keep the current password'}
          >
            <Input.Password placeholder={modalConn === 'new' ? '' : 'unchanged'} autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="display_name" label="Display Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Analytics Warehouse" />
          </Form.Item>
          <Form.Item name="extra_params" label="Additional Parameters (JSON)">
            <Input.TextArea rows={3} placeholder='{"application_name": "abkit"}' style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="ssl" label="SSL" valuePropName="checked">
            <Switch onChange={(checked) => applyDefaultPort(form.getFieldValue('engine'), checked)} />
          </Form.Item>
          <TestConnectionButton getValues={() => form.getFieldsValue()} />
        </Form>
      </Modal>
    </div>
  )
}
