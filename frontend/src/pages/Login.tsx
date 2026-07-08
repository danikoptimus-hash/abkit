import { useState } from 'react'
import { Button, Card, Form, Input, Typography, Alert } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

interface LoginFormValues {
  email: string
  password: string
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

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
      </Card>
    </div>
  )
}
