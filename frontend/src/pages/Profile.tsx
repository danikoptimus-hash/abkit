import { useState } from 'react'
import { Card, Form, Input, Button, Typography, Alert } from 'antd'
import { apiClient, errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'

interface ChangePasswordValues {
  old_password: string
  new_password: string
}

export function ProfilePage() {
  const { user } = useAuth()
  const [form] = Form.useForm<ChangePasswordValues>()
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const onFinish = async (values: ChangePasswordValues) => {
    setSubmitting(true)
    setError(null)
    setSuccess(false)
    try {
      const { error } = await apiClient.POST('/api/v1/auth/change-password', { body: values })
      if (error) throw new Error(errorMessage(error, 'Не удалось сменить пароль'))
      setSuccess(true)
      form.resetFields()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сменить пароль')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card style={{ maxWidth: 420 }}>
      <Typography.Title level={4}>Профиль</Typography.Title>
      <Typography.Paragraph type="secondary">
        {user?.email} · роль {user?.role}
      </Typography.Paragraph>
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {success && <Alert type="success" message="Пароль изменен" showIcon style={{ marginBottom: 16 }} />}
      <Form form={form} layout="vertical" onFinish={onFinish} disabled={submitting}>
        <Form.Item name="old_password" label="Текущий пароль" rules={[{ required: true }]}>
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Form.Item name="new_password" label="Новый пароль" rules={[{ required: true, min: 8 }]}>
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting}>
            Сменить пароль
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}
