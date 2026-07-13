import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { antdTheme } from './theme/tokens'
import { routes } from './App.tsx'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
})

// Data router (not plain <BrowserRouter>) — required for `useBlocker`
// (frontend/src/hooks/useUnsavedGuard.ts), the unsaved-changes guard's
// route-navigation interception (browser back/forward, <Link> clicks,
// programmatic navigate()). AuthProvider has no router-hook dependency of
// its own, so it's fine wrapping RouterProvider from outside rather than
// needing to live inside the routed tree.
const router = createBrowserRouter(routes)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider theme={antdTheme}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </ConfigProvider>
  </StrictMode>,
)
