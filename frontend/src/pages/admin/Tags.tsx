import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Table, Typography, Button, Space, message, Modal, Input, Form, Select, Tag as AntTag, Tooltip } from 'antd'
import {
  EditOutlined, DeleteOutlined, MergeCellsOutlined, CheckSquareOutlined, CloseOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { apiClient, errorMessage } from '../../api/client'
import type { ApiErrorBody } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import { hashColor } from '../../components/hashColor'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { RelativeTime } from '../../components/RelativeTime'
import { BulkDeleteTagsModal } from '../../components/tags/BulkDeleteTagsModal'
import type { BulkDeleteTagsResult } from '../../components/tags/BulkDeleteTagsModal'
import type { components } from '../../api/schema'

type TagAdminOut = components['schemas']['TagAdminOut']

// Every tag mutation on this page (rename/merge/delete/bulk-delete) touches
// data three other places read from a DIFFERENT cache key: the Properties
// modal's tags typeahead, the experiments list's tag filter (both
// tagsTypeaheadAll), and the Tags column on the experiments list itself
// (experimentsAll) — invalidating all three here is this page's own live
// test of the query-key-registry contract (CLAUDE.md, "свежесть данных
// после мутаций"), not just this page's own list.
function invalidateTagCaches(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: queryKeys.adminTagsAll() })
  queryClient.invalidateQueries({ queryKey: queryKeys.tagsTypeaheadAll() })
  queryClient.invalidateQueries({ queryKey: queryKeys.experimentsAll() })
}

function TagNameBadge({ name }: { name: string }) {
  return <AntTag color={hashColor(name)}>{name}</AntTag>
}

// Item 2.1: renaming into a name that collides case-insensitively with a
// DIFFERENT existing tag doesn't just fail — the backend (409
// tag_name_conflict) hands back the existing tag's id/name, and this modal
// offers Merge as the explicit next step instead of a dead-end error.
function RenameTagModal({
  tag, onClose, onRenamed, onOfferMerge,
}: {
  tag: TagAdminOut | null
  onClose: () => void
  onRenamed: () => void
  onOfferMerge: (source: TagAdminOut, targetId: string, targetName: string) => void
}) {
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [conflict, setConflict] = useState<{ id: string; name: string } | null>(null)

  const open = tag !== null

  // Prefilling via Modal's afterOpenChange would race with the open
  // animation — a user who starts typing before the animation finishes
  // could have their input clobbered by the delayed prefill. Keyed on
  // tag?.id instead (same pattern as EditDatasetModal's dataset?.id
  // effect), so it fires synchronously with the prop change, not the
  // animation.
  useEffect(() => {
    if (tag) {
      setName(tag.name)
      setConflict(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tag?.id])

  const handleSave = async () => {
    if (!tag) return
    const trimmed = name.trim()
    if (!trimmed) return
    setSaving(true)
    setConflict(null)
    try {
      const { error } = await apiClient.PATCH('/api/v1/tags/{tag_id}', {
        params: { path: { tag_id: tag.id } },
        body: { name: trimmed },
      })
      if (error) {
        const body = error as ApiErrorBody
        if (body?.error?.code === 'tag_name_conflict') {
          const details = body.error.details as { existing_tag_id: string; existing_tag_name: string }
          setConflict({ id: details.existing_tag_id, name: details.existing_tag_name })
          return
        }
        throw new Error(errorMessage(error))
      }
      message.success('Renamed')
      onRenamed()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Failed to rename')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={`Rename "${tag?.name ?? ''}"`}
      open={open}
      onCancel={onClose}
      onOk={handleSave}
      okText="Rename"
      confirmLoading={saving}
      destroyOnHidden
    >
      <Form layout="vertical">
        <Form.Item label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Form.Item>
      </Form>
      {conflict && (
        <div style={{ background: '#FFF7E6', border: '1px solid #FFD591', borderRadius: 6, padding: 12 }}>
          <Typography.Paragraph style={{ marginBottom: 8 }}>
            A tag named <Typography.Text strong>{conflict.name}</Typography.Text> already exists.
          </Typography.Paragraph>
          <Button
            size="small"
            icon={<MergeCellsOutlined />}
            onClick={() => {
              if (!tag) return
              onOfferMerge(tag, conflict.id, conflict.name)
            }}
          >
            Merge into it instead
          </Button>
        </div>
      )}
    </Modal>
  )
}

// Item 2.3: target picked from the full unfiltered tag list (a dedicated
// query, not the outer table's possibly-search-narrowed one) via typeahead —
// same GET /tags?q= the Properties modal's Tags field already uses.
function MergeTagModal({
  source, presetTargetId, presetTargetName, onClose, onMerged,
}: {
  source: TagAdminOut | null
  presetTargetId?: string
  presetTargetName?: string
  onClose: () => void
  onMerged: () => void
}) {
  const [targetId, setTargetId] = useState<string | undefined>(presetTargetId)
  const [targetSearch, setTargetSearch] = useState('')
  const [merging, setMerging] = useState(false)

  const open = source !== null

  // Same reasoning as RenameTagModal — reset keyed on source?.id (fires
  // synchronously with the prop change) instead of Modal's afterOpenChange
  // (fires after the open animation, racing a fast user selection).
  useEffect(() => {
    if (source) {
      setTargetId(presetTargetId)
      setTargetSearch('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source?.id])

  const { data: options, isFetching } = useQuery({
    queryKey: queryKeys.tagsTypeahead(targetSearch),
    enabled: open,
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/tags', { params: { query: { q: targetSearch || undefined } } })
      if (error) throw new Error(errorMessage(error))
      return data.items.filter((t) => t.id !== source?.id)
    },
  })

  const targetName = presetTargetId === targetId ? presetTargetName : options?.find((o) => o.id === targetId)?.name

  const handleMerge = async () => {
    if (!source || !targetId) return
    setMerging(true)
    try {
      const { error } = await apiClient.POST('/api/v1/tags/{tag_id}/merge', {
        params: { path: { tag_id: source.id } },
        body: { target_id: targetId },
      })
      if (error) throw new Error(errorMessage(error))
      message.success(`Merged "${source.name}" into "${targetName ?? 'target'}"`)
      onMerged()
    } catch (e) {
      message.error(e instanceof Error ? e.message : 'Failed to merge')
    } finally {
      setMerging(false)
    }
  }

  return (
    <Modal
      title={`Merge "${source?.name ?? ''}"`}
      open={open}
      onCancel={onClose}
      onOk={handleMerge}
      okText="Merge"
      okButtonProps={{ disabled: !targetId, loading: merging }}
      destroyOnHidden
    >
      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        Every experiment tagged &quot;{source?.name}&quot; will be re-tagged with the target instead, and &quot;
        {source?.name}&quot; will be deleted.
      </Typography.Paragraph>
      <Select
        style={{ width: '100%', marginBottom: 12 }}
        showSearch
        aria-label="merge-target-select"
        placeholder="Target tag"
        loading={isFetching}
        value={targetId}
        onSearch={setTargetSearch}
        filterOption={false}
        options={(options ?? []).map((t) => ({ value: t.id, label: t.name }))}
        onChange={setTargetId}
      />
      {source && targetId && (
        <Typography.Paragraph>
          Merge &quot;{source.name}&quot; into &quot;{targetName ?? ''}&quot;: {source.experiment_count} experiment
          {source.experiment_count === 1 ? '' : 's'} will be re-tagged.
        </Typography.Paragraph>
      )}
    </Modal>
  )
}

export function TagsAdminPage() {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const debouncedQ = useDebouncedValue(q, 300)

  const [renameTarget, setRenameTarget] = useState<TagAdminOut | null>(null)
  const [mergeTarget, setMergeTarget] = useState<TagAdminOut | null>(null)
  const [mergePreset, setMergePreset] = useState<{ id: string; name: string } | undefined>(undefined)

  const [bulkMode, setBulkMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [bulkDeleteTargets, setBulkDeleteTargets] = useState<TagAdminOut[] | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.adminTags(debouncedQ),
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/tags/admin', { params: { query: { q: debouncedQ || undefined } } })
      if (error) throw new Error(errorMessage(error))
      return data.items
    },
  })

  const exitBulkMode = () => {
    setBulkMode(false)
    setSelectedIds([])
  }

  const handleDelete = (tag: TagAdminOut) => {
    Modal.confirm({
      title: `Delete tag "${tag.name}"?`,
      content:
        tag.experiment_count > 0
          ? `It will be removed from ${tag.experiment_count} experiment${tag.experiment_count === 1 ? '' : 's'}.`
          : 'It is not used by any experiment.',
      okText: 'Delete',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          const { error } = await apiClient.DELETE('/api/v1/tags/{tag_id}', { params: { path: { tag_id: tag.id } } })
          if (error) throw new Error(errorMessage(error))
          message.success(`Deleted "${tag.name}"`)
          invalidateTagCaches(queryClient)
        } catch (e) {
          message.error(e instanceof Error ? e.message : 'Failed to delete')
        }
      },
    })
  }

  const handleBulkDeleteDone = (result: BulkDeleteTagsResult) => {
    setBulkDeleteTargets(null)
    exitBulkMode()
    invalidateTagCaches(queryClient)
    if (result.skipped.length === 0) {
      message.success(`Deleted ${result.deleted.length} tag${result.deleted.length === 1 ? '' : 's'}`)
    } else {
      Modal.info({
        title: 'Bulk delete finished',
        content: <p>Deleted {result.deleted.length}, skipped {result.skipped.length} (not found).</p>,
      })
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Tags
        </Typography.Title>
        <Space>
          <Button
            icon={bulkMode ? <CloseOutlined /> : <CheckSquareOutlined />}
            onClick={() => (bulkMode ? exitBulkMode() : setBulkMode(true))}
          >
            {bulkMode ? 'Cancel' : 'Bulk select'}
          </Button>
        </Space>
      </Space>

      <Input
        allowClear
        placeholder="Search tags..."
        style={{ width: 280, marginBottom: 16 }}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      {bulkMode && selectedIds.length > 0 && (
        <Space style={{ marginBottom: 12, padding: '8px 12px', background: '#F0F5F3', borderRadius: 6 }}>
          <span>{selectedIds.length} selected</span>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            aria-label="Delete selected"
            onClick={() => setBulkDeleteTargets((data ?? []).filter((t) => selectedIds.includes(t.id)))}
          >
            Delete
          </Button>
          <Button size="small" onClick={exitBulkMode}>
            Deselect all
          </Button>
        </Space>
      )}

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data ?? []}
        rowSelection={
          bulkMode
            ? { selectedRowKeys: selectedIds, onChange: (keys) => setSelectedIds(keys as string[]) }
            : undefined
        }
        pagination={false}
        columns={[
          {
            title: 'Tag',
            dataIndex: 'name',
            sorter: (a: TagAdminOut, b: TagAdminOut) => a.name.localeCompare(b.name),
            render: (name: string) => <TagNameBadge name={name} />,
          },
          {
            title: 'Experiments',
            dataIndex: 'experiment_count',
            sorter: (a: TagAdminOut, b: TagAdminOut) => a.experiment_count - b.experiment_count,
            defaultSortOrder: 'descend',
            render: (count: number, record: TagAdminOut) =>
              count > 0 ? <Link to={`/experiments?tag=${record.id}`}>{count}</Link> : count,
          },
          { title: 'Created by', dataIndex: 'created_by_email', render: (email: string | null) => email ?? '—' },
          { title: 'Created', dataIndex: 'created_at', render: (ts: string) => <RelativeTime iso={ts} /> },
          {
            title: 'Actions',
            key: 'actions',
            render: (_, record: TagAdminOut) => (
              <Space size={4}>
                <Tooltip title="Rename">
                  <Button
                    className="hover-actions"
                    size="small"
                    aria-label="Rename"
                    icon={<EditOutlined />}
                    onClick={() => setRenameTarget(record)}
                  />
                </Tooltip>
                <Tooltip title="Merge">
                  <Button
                    className="hover-actions"
                    size="small"
                    aria-label="Merge"
                    icon={<MergeCellsOutlined />}
                    onClick={() => {
                      setMergePreset(undefined)
                      setMergeTarget(record)
                    }}
                  />
                </Tooltip>
                <Tooltip title="Delete">
                  <Button
                    className="hover-actions"
                    danger
                    size="small"
                    aria-label="Delete"
                    icon={<DeleteOutlined />}
                    onClick={() => handleDelete(record)}
                  />
                </Tooltip>
              </Space>
            ),
          },
        ]}
      />

      <RenameTagModal
        tag={renameTarget}
        onClose={() => setRenameTarget(null)}
        onRenamed={() => {
          setRenameTarget(null)
          invalidateTagCaches(queryClient)
        }}
        onOfferMerge={(source, targetId, targetName) => {
          setRenameTarget(null)
          setMergePreset({ id: targetId, name: targetName })
          setMergeTarget(source)
        }}
      />

      <MergeTagModal
        source={mergeTarget}
        presetTargetId={mergePreset?.id}
        presetTargetName={mergePreset?.name}
        onClose={() => setMergeTarget(null)}
        onMerged={() => {
          setMergeTarget(null)
          invalidateTagCaches(queryClient)
        }}
      />

      <BulkDeleteTagsModal
        tags={bulkDeleteTargets}
        onCancel={() => setBulkDeleteTargets(null)}
        onDone={handleBulkDeleteDone}
      />
    </div>
  )
}
