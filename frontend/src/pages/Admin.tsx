import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Table, Button, Modal, Form, Input, Select, Switch, message, Typography, Space, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { apiClient, errorMessage } from '../api/client'
import type { components } from '../api/schema'

type UserAdminOut = components['schemas']['UserAdminOut']

interface UserFormValues {
  email: string
  name: string
  role: string
  is_active: boolean
}

export function AdminPage() {
  const queryClient = useQueryClient()
  const [modalUser, setModalUser] = useState<UserAdminOut | 'new' | null>(null)
  const [form] = Form.useForm<UserFormValues>()
  const [saving, setSaving] = useState(false)

  const { data: users, isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/admin/users')
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  const openEdit = (user: UserAdminOut) => {
    setModalUser(user)
    form.setFieldsValue({ email: user.email, name: user.name, role: user.role, is_active: user.is_active })
  }

  const openCreate = () => {
    setModalUser('new')
    form.resetFields()
    form.setFieldsValue({ role: 'viewer', is_active: true })
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      if (modalUser === 'new') {
        const { data, error } = await apiClient.POST('/api/v1/admin/users', {
          body: { email: values.email, name: values.name, role: values.role },
        })
        if (error) throw new Error(errorMessage(error))
        Modal.info({
          title: 'Пользователь создан',
          content: (
            <Typography.Paragraph>
              Временный пароль (сообщите пользователю, он будет предложено сменить его при первом
              входе): <Typography.Text code copyable>{data.generated_password}</Typography.Text>
            </Typography.Paragraph>
          ),
        })
      } else if (modalUser) {
        const { error } = await apiClient.PATCH('/api/v1/admin/users/{user_id}', {
          params: { path: { user_id: modalUser.id } },
          body: { name: values.name, role: values.role, is_active: values.is_active },
        })
        if (error) throw new Error(errorMessage(error))
      }
      message.success('Сохранено')
      setModalUser(null)
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  const handleResetPassword = async (user: UserAdminOut) => {
    const { data, error } = await apiClient.POST('/api/v1/admin/users/{user_id}/reset-password', {
      params: { path: { user_id: user.id } },
    })
    if (error) {
      message.error(errorMessage(error))
      return
    }
    Modal.info({
      title: `Новый пароль для ${user.email}`,
      content: (
        <Typography.Paragraph>
          <Typography.Text code copyable>{data.new_password}</Typography.Text>
        </Typography.Paragraph>
      ),
    })
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Пользователи
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Создать пользователя
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={users ?? []}
        columns={[
          { title: 'Email', dataIndex: 'email' },
          { title: 'Имя', dataIndex: 'name' },
          { title: 'Роль', dataIndex: 'role' },
          {
            title: 'Активен',
            dataIndex: 'is_active',
            render: (active: boolean) => <Tag color={active ? 'success' : 'default'}>{active ? 'да' : 'нет'}</Tag>,
          },
          {
            title: 'Действия',
            key: 'actions',
            render: (_, record: UserAdminOut) => (
              <Space>
                <Button size="small" onClick={() => openEdit(record)}>
                  Изменить
                </Button>
                <Button size="small" onClick={() => handleResetPassword(record)}>
                  Сбросить пароль
                </Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={modalUser === 'new' ? 'Новый пользователь' : `Изменить ${(modalUser as UserAdminOut)?.email ?? ''}`}
        open={modalUser !== null}
        onCancel={() => setModalUser(null)}
        onOk={handleSave}
        confirmLoading={saving}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="email" label="Email" rules={[{ required: true }]}>
            <Input disabled={modalUser !== 'new'} />
          </Form.Item>
          <Form.Item name="name" label="Имя" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="role" label="Роль" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'viewer', label: 'viewer' },
                { value: 'editor', label: 'editor' },
                { value: 'admin', label: 'admin' },
              ]}
            />
          </Form.Item>
          {modalUser !== 'new' && (
            <Form.Item
              name="is_active"
              label="Активен"
              valuePropName="checked"
              extra="Лучше деактивировать, чем удалять"
            >
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
