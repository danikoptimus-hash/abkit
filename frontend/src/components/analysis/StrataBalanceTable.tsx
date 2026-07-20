import { Typography, Tag, Table, Collapse } from 'antd'
import { useAuth } from '../../auth/AuthContext'
import type { StrataBalance } from '../../pages/experiment/analyzeTypes'

// §3: strata balance table, collapsed by default when it has many strata
// (> 12). The summary line always shows the verdict; the expanded/collapsed
// choice persists per-user (users.strata_balance_expanded), like the folders
// panel. A short table (<= 12) always renders expanded — nothing to collapse.
const COLLAPSE_THRESHOLD = 12

export function StrataBalanceTable({ balance }: { balance: StrataBalance }) {
  const { user, updatePreferences } = useAuth()

  const summary = `${balance.rows.length} strata · balance chi-square p=${balance.p_value.toExponential(2)} · ${
    balance.passed ? 'passed' : 'failed'
  }`

  const table = (
    <>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
        Group × stratum composition on the analyzed users — was the split balanced across the declared strata?
      </Typography.Paragraph>
      <Table
        size="small"
        pagination={false}
        dataSource={balance.rows.map((r, i) => ({ key: i, ...r }))}
        columns={[
          { title: 'Stratum', dataIndex: 'stratum' },
          ...balance.groups.map((g) => ({ title: g, dataIndex: g })),
        ]}
      />
    </>
  )

  const header = (
    <Typography.Text strong>
      Stratum balance{' '}
      <Tag color={balance.passed ? 'success' : 'error'}>
        {summary}
      </Tag>
    </Typography.Text>
  )

  if (balance.rows.length <= COLLAPSE_THRESHOLD) {
    return (
      <div style={{ marginTop: 16, marginBottom: 8 }}>
        <div style={{ marginBottom: 8 }}>{header}</div>
        {table}
      </div>
    )
  }

  const expanded = user?.strata_balance_expanded ?? false
  const onChange = (keys: string | string[]) => {
    const isOpen = (Array.isArray(keys) ? keys : [keys]).includes('balance')
    void updatePreferences({ strata_balance_expanded: isOpen }).catch(() => {})
  }

  return (
    <div style={{ marginTop: 16, marginBottom: 8 }}>
      <Collapse
        activeKey={expanded ? ['balance'] : []}
        onChange={onChange}
        items={[{ key: 'balance', label: header, children: table }]}
      />
    </div>
  )
}
