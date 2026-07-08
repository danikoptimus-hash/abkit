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
  if (minRole && !hasMinRole(user, minRole)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
