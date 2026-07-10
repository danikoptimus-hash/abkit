// Edit dataset modal (UX package, Datasets §1.2) — best-effort prefill for
// the schema/table selects from a saved `sql_text`. Deliberately only
// handles the simple "FROM schema.table" shape (bare or double-quoted
// identifiers); anything with a JOIN, subquery, or unqualified table name is
// left unparsed rather than guessed at, so the selects just stay empty.
const IDENT = '(?:"([^"]+)"|(\\w+))'
const FROM_SCHEMA_TABLE_RE = new RegExp(`\\bFROM\\s+${IDENT}\\.${IDENT}\\b`, 'i')

export function parseSchemaTableFromSql(sql: string): { schema?: string; table?: string } {
  if (!sql.trim() || /\bJOIN\b/i.test(sql)) return {}
  const match = sql.match(FROM_SCHEMA_TABLE_RE)
  if (!match) return {}
  const schema = match[1] ?? match[2]
  const table = match[3] ?? match[4]
  if (!schema || !table) return {}
  return { schema, table }
}
