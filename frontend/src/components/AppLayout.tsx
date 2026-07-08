import { Layout, Menu, Dropdown, Avatar, Space } from 'antd'
import { UserOutlined, DownOutlined } from '@ant-design/icons'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const { Header, Content } = Layout

// Верхняя навигация как Dashboards/Charts/Datasets в Superset (FRONTEND.md §1).
const NAV_ITEMS = [
  { key: '/experiments', label: <Link to="/experiments">A/B тесты</Link> },
  { key: '/datasets', label: <Link to="/datasets">Датасеты</Link> },
  { key: '/validation', label: <Link to="/validation">Валидация</Link> },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const selectedKey = NAV_ITEMS.find((item) => location.pathname.startsWith(item.key))?.key ?? ''

  const userMenuItems = [
    { key: 'profile', label: <Link to="/profile">Профиль</Link> },
    ...(user?.role === 'admin'
      ? [
          { key: 'admin', label: <Link to="/admin">Admin</Link> },
          { key: 'audit', label: <Link to="/audit">Аудит</Link> },
        ]
      : []),
    { key: 'logout', label: 'Выйти' },
  ]

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout().then(() => navigate('/login'))
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', background: '#fff', borderBottom: '1px solid #E0E0E0' }}>
        <div style={{ fontWeight: 700, fontSize: 18, color: '#2E8B6D', marginRight: 32 }}>abkit</div>
        <Menu mode="horizontal" selectedKeys={[selectedKey]} items={NAV_ITEMS} style={{ flex: 1, borderBottom: 'none' }} />
        {user && (
          <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenuClick }} trigger={['click']}>
            <Space style={{ cursor: 'pointer' }} data-testid="user-menu-trigger">
              <Avatar size="small" icon={<UserOutlined />} />
              {user.name || user.email}
              <DownOutlined style={{ fontSize: 10 }} />
            </Space>
          </Dropdown>
        )}
      </Header>
      <Content style={{ padding: 24 }}>
        <Outlet />
      </Content>
    </Layout>
  )
}
