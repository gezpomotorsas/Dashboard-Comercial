import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil, Plus, Trash2 } from 'lucide-react'
import { GroupPerformanceCompare } from '@/components/deal-analytics/GroupPerformanceCompare'
import { AdvisorVsTeamCharts } from '@/components/deal-analytics/AdvisorVsTeamCharts'
import { PaginatedMetricTable } from '@/components/deal-analytics/PaginatedMetricTable'
import { ErrorState } from '@/components/ui/ErrorState'
import {
  useAdvisorGroupMutations,
  useAdvisorGroups,
  useGroupsCompare,
  useHubSpotTeams,
} from '@/hooks/useAdvisorGroups'
import { useBrandOperating, type OperatingBrand } from '@/hooks/useBrandOperating'
import { advisorPortfolioPath } from '@/lib/advisorRoutes'
import {
  defaultCompareReferenceKey,
  listCompareReferenceOptions,
  resolveCompareReference,
} from '@/lib/advisorTeamCompare'
import { staleMetricShortLabel, staleMetricTooltip } from '@/lib/brandStale'
import { formatPercent } from '@/lib/format'
import type { AdvisorGroup, GroupCompareRow } from '@/types/advisorGroups'

const BRANDS: { id: OperatingBrand; label: string }[] = [
  { id: 'voyah', label: 'Voyah' },
  { id: 'mhero', label: 'MHero' },
  { id: 'shacman', label: 'Shacman' },
]

const GROUP_TABLE_COLUMN_DEFS = [
  { label: 'Grupo', tooltip: 'Nombre del grupo de asesores.' },
  { label: 'Miembros', tooltip: 'Cantidad de asesores en el grupo.' },
  { label: 'Abiertos', tooltip: 'Negocios abiertos del grupo en la marca.' },
  { label: '__STALE__', tooltip: '__STALE__' },
  { label: 'Cob. llamadas', tooltip: 'Cobertura de llamadas en ventana 21d (agregación grupal).' },
  { label: 'Cob. WhatsApp', tooltip: 'Cobertura WhatsApp en ventana 21d.' },
  { label: 'Cob. combinada', tooltip: 'Cobertura combinada llamada y/o WhatsApp.' },
  { label: 'Atrasados 21d', tooltip: 'Negocios activos sin contacto en 21 días.' },
  { label: 'Tareas venc.', tooltip: 'Tareas vencidas agregadas del grupo.' },
]

function buildGroupTableColumns(brand: OperatingBrand, staleDays?: number) {
  const staleLabel = staleMetricShortLabel(brand, staleDays)
  const staleTooltip = staleMetricTooltip(brand, staleDays)
  return GROUP_TABLE_COLUMN_DEFS.map((col) =>
    col.label === '__STALE__' ? { label: staleLabel, tooltip: staleTooltip } : col,
  )
}

function groupCoverageCells(g: GroupCompareRow) {
  const cm = g.contact_methodology
  return [
    cm?.calls?.call_coverage_rate != null ? formatPercent(cm.calls.call_coverage_rate) : '—',
    cm?.whatsapp?.whatsapp_coverage_rate != null ? formatPercent(cm.whatsapp.whatsapp_coverage_rate) : '—',
    cm?.coverage?.combined_contact_coverage_rate != null
      ? formatPercent(cm.coverage.combined_contact_coverage_rate)
      : '—',
    cm?.coverage?.overdue_contact_21d ?? '—',
  ]
}

function sourceLabel(source: string | undefined): string {
  if (source === 'hubspot_team') return 'Team HubSpot'
  if (source === 'hubspot_list') return 'Lista HubSpot'
  return 'Manual'
}

export function GrupoPage() {
  const navigate = useNavigate()
  const params = useParams<{ groupId?: string }>()
  const [brand, setBrand] = useState<OperatingBrand>('shacman')
  const [selectedGroupIds, setSelectedGroupIds] = useState<Set<string>>(new Set())
  const [editingGroup, setEditingGroup] = useState<AdvisorGroup | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formMembers, setFormMembers] = useState<Set<string>>(new Set())
  const [importTeamId, setImportTeamId] = useState('')
  const [selectedAdvisorId, setSelectedAdvisorId] = useState('')
  const [compareReferenceKey, setCompareReferenceKey] = useState('')

  const groupsQuery = useAdvisorGroups()
  const teamsQuery = useHubSpotTeams()
  const operatingQuery = useBrandOperating(brand)
  const mutations = useAdvisorGroupMutations()

  const compareIds = useMemo(() => Array.from(selectedGroupIds), [selectedGroupIds])
  const compareQuery = useGroupsCompare(brand, compareIds.length > 0 ? compareIds : [])

  const groups = groupsQuery.data ?? []
  const advisors = operatingQuery.data?.data.advisors ?? []
  const comparedGroups = compareQuery.data?.data.groups ?? []
  const selectedAdvisor = advisors.find((a) => (a.owner_id ?? 'unassigned') === selectedAdvisorId) ?? null
  const brandLabel = operatingQuery.data?.data.brand_label ?? brand.toUpperCase()
  const staleDays = operatingQuery.data?.data.stale_threshold_days
  const groupTableColumns = useMemo(
    () => buildGroupTableColumns(brand, staleDays),
    [brand, staleDays],
  )
  const staleColumnLabel = staleMetricShortLabel(brand, staleDays)
  const compareReferenceOptions = useMemo(
    () => listCompareReferenceOptions(teamsQuery.data ?? [], groups, brandLabel),
    [teamsQuery.data, groups, brandLabel],
  )
  const compareReference = useMemo(
    () => resolveCompareReference(compareReferenceKey, compareReferenceOptions),
    [compareReferenceKey, compareReferenceOptions],
  )

  useEffect(() => {
    if (!selectedAdvisorId) {
      setCompareReferenceKey('')
      return
    }
    setCompareReferenceKey(
      defaultCompareReferenceKey(selectedAdvisorId, teamsQuery.data ?? [], groups),
    )
  }, [selectedAdvisorId, brand])

  useEffect(() => {
    if (!selectedAdvisorId || compareReferenceKey) return
    const key = defaultCompareReferenceKey(selectedAdvisorId, teamsQuery.data ?? [], groups)
    if (key) setCompareReferenceKey(key)
  }, [selectedAdvisorId, compareReferenceKey, teamsQuery.data, groups])

  const activeGroup = params.groupId ? groups.find((g) => g.id === params.groupId) : null

  function toggleCompareGroup(id: string) {
    setSelectedGroupIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < 8) next.add(id)
      return next
    })
  }

  function openCreate() {
    setEditingGroup(null)
    setFormName('')
    setFormDescription('')
    setFormMembers(new Set())
    setShowCreate(true)
  }

  function openEdit(group: AdvisorGroup) {
    setEditingGroup(group)
    setFormName(group.name)
    setFormDescription(group.description ?? '')
    setFormMembers(new Set(group.members.map((m) => m.owner_id)))
    setShowCreate(true)
  }

  async function saveGroup() {
    const members = Array.from(formMembers).map((ownerId) => {
      const adv = advisors.find((a) => (a.owner_id ?? 'unassigned') === ownerId)
      return { owner_id: ownerId, owner_name: adv?.owner_name ?? null }
    })
    const body = {
      name: formName.trim(),
      description: formDescription.trim() || null,
      brand_value: brand,
      members,
    }
    if (!body.name) return
    if (editingGroup) {
      await mutations.update.mutateAsync({ id: editingGroup.id, body })
    } else {
      await mutations.create.mutateAsync(body)
    }
    setShowCreate(false)
  }

  async function handleDelete(groupId: string) {
    if (!window.confirm('¿Eliminar este grupo?')) return
    await mutations.remove.mutateAsync(groupId)
    setSelectedGroupIds((prev) => {
      const next = new Set(prev)
      next.delete(groupId)
      return next
    })
    if (params.groupId === groupId) navigate('/grupo')
  }

  async function handleImportTeam() {
    if (!importTeamId) return
    await mutations.importTeam.mutateAsync({ teamId: importTeamId, brand })
    setImportTeamId('')
  }

  if (groupsQuery.error) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <ErrorState
          title="No se pudieron cargar los grupos"
          message={groupsQuery.error instanceof Error ? groupsQuery.error.message : 'Error de API'}
          onRetry={() => void groupsQuery.refetch()}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white px-6 py-5">
        <Link
          to="/"
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Volver a operación por marca
        </Link>
        <p className="text-sm uppercase tracking-wide text-blue-600">Comparación por grupos</p>
        <h1 className="text-2xl font-semibold">Grupos de asesores</h1>
        <p className="text-slate-600">
          Agrupa asesores, importa teams de HubSpot y compara grupos o un asesor contra la media de sus
          compañeros.
        </p>
      </header>

      <div className="border-b bg-white px-6 py-4">
        <nav className="flex flex-wrap gap-2">
          {BRANDS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setBrand(item.id)
                setSelectedAdvisorId('')
                setCompareReferenceKey('')
              }}
              className={`rounded-full px-5 py-2.5 text-sm font-medium ${
                brand === item.id ? 'bg-blue-600 text-white shadow-sm' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      <main className="grid gap-6 p-6 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-4">
          <section className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-medium">Mis grupos</h2>
              <button
                type="button"
                onClick={openCreate}
                className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white"
              >
                <Plus className="h-3.5 w-3.5" />
                Nuevo
              </button>
            </div>
            {groupsQuery.isLoading ? (
              <p className="text-sm text-slate-500">Cargando…</p>
            ) : groups.length === 0 ? (
              <p className="text-sm text-slate-500">Sin grupos. Crea uno o importa desde HubSpot.</p>
            ) : (
              <ul className="space-y-2">
                {groups.map((group) => (
                  <li
                    key={group.id}
                    className={`rounded-lg border p-3 ${
                      selectedGroupIds.has(group.id) ? 'border-blue-400 bg-blue-50' : 'border-slate-200'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked={selectedGroupIds.has(group.id)}
                        onChange={() => toggleCompareGroup(group.id)}
                        className="mt-1"
                        aria-label={`Comparar ${group.name}`}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{group.name}</p>
                        <p className="text-xs text-slate-500">
                          {group.member_count} asesores · {sourceLabel(group.source)}
                        </p>
                      </div>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(group)}
                          className="rounded p-1 text-slate-500 hover:bg-slate-100"
                          aria-label="Editar"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(group.id)}
                          className="rounded p-1 text-red-500 hover:bg-red-50"
                          aria-label="Eliminar"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-xl border bg-white p-4 shadow-sm">
            <h2 className="mb-2 font-medium">Importar desde HubSpot</h2>
            <p className="mb-3 text-xs text-slate-500">Teams sincronizados desde owners en HubSpot.</p>
            <label className="block text-xs font-medium text-slate-600">Team HubSpot</label>
            <select
              className="mt-1 mb-2 w-full rounded-lg border px-2 py-1.5 text-sm"
              value={importTeamId}
              onChange={(e) => setImportTeamId(e.target.value)}
            >
              <option value="">Seleccionar team…</option>
              {(teamsQuery.data ?? []).map((t) => (
                <option key={t.team_id} value={t.team_id}>
                  {t.team_name} ({t.member_count})
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!importTeamId || mutations.importTeam.isPending}
              onClick={() => void handleImportTeam()}
              className="w-full rounded-lg border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40"
            >
              Importar team
            </button>
          </section>

          <section className="rounded-xl border bg-white p-4 shadow-sm">
            <h2 className="mb-2 font-medium">Asesor vs media del equipo</h2>
            <p className="mb-3 text-xs text-slate-500">
              Compara ventas, leads, tareas y contacto del mes contra el promedio del equipo de referencia.
            </p>
            <label className="block text-xs font-medium text-slate-600">Asesor en {brand.toUpperCase()}</label>
            <select
              className="mt-1 mb-3 w-full rounded-lg border px-2 py-1.5 text-sm"
              value={selectedAdvisorId}
              onChange={(e) => setSelectedAdvisorId(e.target.value)}
              disabled={operatingQuery.isLoading}
            >
              <option value="">Seleccionar asesor…</option>
              {[...advisors]
                .sort(
                  (a, b) =>
                    b.open_deals - a.open_deals || (a.owner_name ?? '').localeCompare(b.owner_name ?? ''),
                )
                .map((adv) => {
                  const id = adv.owner_id ?? 'unassigned'
                  return (
                    <option key={id} value={id}>
                      {adv.owner_name ?? 'Sin asignar'} ({adv.open_deals} abiertos)
                    </option>
                  )
                })}
            </select>
            <label className="block text-xs font-medium text-slate-600">Equipo de referencia</label>
            <select
              className="mt-1 mb-2 w-full rounded-lg border px-2 py-1.5 text-sm"
              value={compareReferenceKey}
              onChange={(e) => setCompareReferenceKey(e.target.value)}
              disabled={!selectedAdvisorId || compareReferenceOptions.length === 0}
            >
              <option value="">Seleccionar equipo…</option>
              {compareReferenceOptions.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
            {selectedAdvisor && compareReference ? (
              <p className="text-xs text-slate-500">
                Comparando con la media de compañeros en{' '}
                <span className="font-medium text-slate-700">{compareReference.name}</span>.
              </p>
            ) : selectedAdvisor ? (
              <p className="text-xs text-slate-400">Selecciona el equipo contra el que quieres comparar.</p>
            ) : (
              <p className="text-xs text-slate-400">Primero elige un asesor.</p>
            )}
          </section>
        </aside>

        <div className="space-y-6">
          {selectedAdvisor && compareReference ? (
            operatingQuery.isLoading ? (
              <div className="h-48 animate-pulse rounded-xl border bg-white" />
            ) : (
              <AdvisorVsTeamCharts
                advisor={selectedAdvisor}
                advisors={advisors}
                compareReference={compareReference}
                brandKey={brand}
                brandLabel={brandLabel}
              />
            )
          ) : null}

          {showCreate ? (
            <section className="rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-lg font-medium">
                {editingGroup ? 'Editar grupo' : 'Nuevo grupo'}
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block text-sm">
                  Nombre
                  <input
                    className="mt-1 w-full rounded-lg border px-3 py-2"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                  />
                </label>
                <label className="block text-sm">
                  Descripción
                  <input
                    className="mt-1 w-full rounded-lg border px-3 py-2"
                    value={formDescription}
                    onChange={(e) => setFormDescription(e.target.value)}
                  />
                </label>
              </div>
              <p className="mb-2 mt-4 text-sm font-medium">Asesores en {brand.toUpperCase()}</p>
              <div className="max-h-56 overflow-y-auto rounded-lg border p-3">
                {advisors.map((adv) => {
                  const id = adv.owner_id ?? 'unassigned'
                  return (
                    <label key={id} className="flex items-center gap-2 py-1 text-sm">
                      <input
                        type="checkbox"
                        checked={formMembers.has(id)}
                        onChange={() => {
                          setFormMembers((prev) => {
                            const next = new Set(prev)
                            if (next.has(id)) next.delete(id)
                            else next.add(id)
                            return next
                          })
                        }}
                      />
                      {adv.owner_name ?? 'Sin asignar'} ({adv.open_deals} abiertos)
                    </label>
                  )
                })}
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  type="button"
                  onClick={() => void saveGroup()}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white"
                >
                  Guardar
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="rounded-lg border px-4 py-2 text-sm"
                >
                  Cancelar
                </button>
              </div>
            </section>
          ) : null}

          {compareIds.length === 0 && !(selectedAdvisor && compareReference) ? (
            <section className="rounded-xl border bg-white p-8 text-center shadow-sm">
              <p className="text-slate-600">
                Selecciona uno o más grupos, o un asesor en el panel izquierdo, para comparar en{' '}
                {brand.toUpperCase()}.
              </p>
            </section>
          ) : compareIds.length === 0 ? null : compareQuery.isLoading ? (
            <div className="h-48 animate-pulse rounded-xl border bg-white" />
          ) : compareQuery.error ? (
            <ErrorState
              title="No se pudo comparar grupos"
              message={compareQuery.error instanceof Error ? compareQuery.error.message : 'Error'}
              onRetry={() => void compareQuery.refetch()}
            />
          ) : (
            <>
              <section className="rounded-xl border bg-white p-5 shadow-sm">
                <h2 className="mb-1 text-lg font-medium">
                  Comparación en {compareQuery.data?.data.brand_label ?? brand.toUpperCase()}
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  {compareIds.length} grupo(s) seleccionado(s)
                </p>
                <GroupPerformanceCompare groups={comparedGroups} />
              </section>

              <PaginatedMetricTable
                title="Resumen por grupo"
                columns={groupTableColumns}
                rows={comparedGroups.map((g) => [
                  g.group_name,
                  g.member_count,
                  g.open_deals,
                  g.stale_45d_open,
                  ...groupCoverageCells(g),
                  g.tasks_overdue,
                ])}
                resetKey={compareIds.join(',')}
              />

              {comparedGroups.map((group) => (
                <section key={group.group_id} className="rounded-xl border bg-white p-5 shadow-sm">
                  <h3 className="mb-3 font-medium">
                    {group.group_name} — asesores ({group.advisors.length})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-slate-500">
                          <th className="px-2 py-2">Asesor</th>
                          <th className="px-2 py-2">Abiertos</th>
                          <th className="px-2 py-2">{staleColumnLabel}</th>
                          <th className="px-2 py-2">Cob. llamadas</th>
                          <th className="px-2 py-2">Cob. combinada</th>
                          <th className="px-2 py-2">Tareas venc.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.advisors.map((adv) => (
                          <tr key={adv.owner_id ?? adv.owner_name} className="border-b">
                            <td className="px-2 py-2">
                              {adv.owner_id ? (
                                <Link
                                  to={advisorPortfolioPath(brand, adv.owner_id)}
                                  className="text-blue-600 hover:underline"
                                >
                                  {adv.owner_name}
                                </Link>
                              ) : (
                                adv.owner_name
                              )}
                            </td>
                            <td className="px-2 py-2">{adv.open_deals}</td>
                            <td className="px-2 py-2">{adv.stale_45d_open}</td>
                            <td className="px-2 py-2">
                              {adv.call_coverage_rate != null ? formatPercent(adv.call_coverage_rate) : '—'}
                            </td>
                            <td className="px-2 py-2">
                              {adv.combined_coverage_rate != null ? formatPercent(adv.combined_coverage_rate) : '—'}
                            </td>
                            <td className="px-2 py-2">{adv.tasks_overdue}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}
            </>
          )}

          {activeGroup ? (
            <section className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
              Vista detalle de grupo por URL pendiente de ampliar. Grupo: {activeGroup.name}
            </section>
          ) : null}
        </div>
      </main>
    </div>
  )
}
