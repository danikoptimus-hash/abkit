import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Spin } from 'antd'
import { hasMinRole, useAuth } from './AuthContext'

export function RequireAuth({
  children,
  minRole,
}: {
  children: ReactNode
  minRole?: string
}) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
        <Spin size="large" />
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  // Принудительная смена пароля (как в legacy _render_force_password_change,
  // app.py) — пока флаг взведен, любой переход бросает на /profile (там же
  // форма смены пароля), остальные страницы недоступны.
  if (user.must_change_password && location.pathname !== '/profile') {
    return <Navigate to="/profile" replace />
  }
  if (minRole && !hasMinRole(user, minRole)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
