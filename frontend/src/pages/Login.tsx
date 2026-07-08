import { useState } from 'react'
import { Button, Card, Form, Input, Typography, Alert, Collapse } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { apiClient, errorMessage } from '../api/client'

interface LoginFormValues {
  email: string
  password: string
}

interface RegisterFormValues {
  email: string
  name: string
  password: string
}

function SelfRegisterForm() {
  const [form] = Form.useForm<RegisterFormValues>()
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const onFinish = async (values: RegisterFormValues) => {
    setSubmitting(true)
    setError(null)
    setSuccess(false)
    try {
      const { error } = await apiClient.POST('/api/v1/auth/register', { body: values })
      if (error) throw new Error(errorMessage(error, 'Не удалось зарегистрироваться'))
      setSuccess(true)
      form.resetFields()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось зарегистрироваться')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {success && (
        <Alert
          type="success"
          message="Аккаунт создан (роль Viewer). Теперь войдите выше."
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      <Form form={form} layout="vertical" onFinish={onFinish} disabled={submitting}>
        <Form.Item name="email" label="Email" rules={[{ required: true, message: 'Введите email' }]}>
          <Input autoComplete="username" />
        </Form.Item>
        <Form.Item name="name" label="Имя" rules={[{ required: true, message: 'Введите имя' }]}>
          <Input autoComplete="name" />
        </Form.Item>
        <Form.Item name="password" label="Пароль" rules={[{ required: true, min: 8, message: 'Минимум 8 символов' }]}>
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Form.Item>
          <Button htmlType="submit" block loading={submitting}>
            Создать аккаунт
          </Button>
        </Form.Item>
      </Form>
    </>
  )
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { data: config } = useQuery({
    queryKey: ['auth-config'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/auth/config')
      if (error) throw new Error(errorMessage(error))
      return data
    },
  })

  const from = (location.state as { from?: Location })?.from?.pathname ?? '/experiments'

  const onFinish = async (values: LoginFormValues) => {
    setSubmitting(true)
    setError(null)
    try {
      await login(values.email, values.password)
      navigate(from, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось войти')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#F7F7F7' }}>
      <Card style={{ width: 360 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Typography.Title level={3} style={{ color: '#2E8B6D', marginBottom: 0 }}>
            abkit
          </Typography.Title>
          <Typography.Text type="secondary">Вход в систему</Typography.Text>
        </div>
        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
        <Form layout="vertical" onFinish={onFinish} disabled={submitting}>
          <Form.Item name="email" label="Email" rules={[{ required: true, message: 'Введите email' }]}>
            <Input autoFocus autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="Пароль" rules={[{ required: true, message: 'Введите пароль' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={submitting}>
              Войти
            </Button>
          </Form.Item>
        </Form>
        {config?.self_registration_enabled && (
          <Collapse
            ghost
            style={{ marginTop: 8 }}
            items={[{ key: 'register', label: 'Зарегистрироваться', children: <SelfRegisterForm /> }]}
          />
        )}
      </Card>
    </div>
  )
}
