import { Result } from 'antd'

// Заглушка — полная форма валидации (эксперимент/датасет/n_sims/effect) +
// результаты (FPR, распределение p-value, мощность эмпирическая vs
// аналитическая) — R6 (FRONTEND.md §5.2 "/validation"). API уже готово (R3:
// POST /experiments/{name}/validate).
export function ValidationStubPage() {
  return (
    <Result
      status="info"
      title="Валидация (A/A, A/B)"
      subTitle="Форма и результаты будут реализованы на этапе R6 (FRONTEND.md)."
    />
  )
}
