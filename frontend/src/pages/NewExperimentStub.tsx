import { Result, Button } from 'antd'
import { useNavigate } from 'react-router-dom'

// Заглушка (FRONTEND.md §7 R4: "/experiments список, без визарда — кнопка
// ведет на заглушку"). Полный 4-шаговый визард дизайна — R5.
export function NewExperimentStubPage() {
  const navigate = useNavigate()
  return (
    <Result
      status="info"
      title="Визард дизайна A/B теста"
      subTitle="Будет реализован на этапе R5 (FRONTEND.md)."
      extra={
        <Button type="primary" onClick={() => navigate('/experiments')}>
          Назад к списку
        </Button>
      }
    />
  )
}
