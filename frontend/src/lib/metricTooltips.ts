export type MetricColumn = {
  label: string
  tooltip: string
  /** Agrupa columnas bajo un encabezado visual */
  group?: 'Cartera' | 'Tareas' | 'Contacto' | 'Ventas' | 'Leads'
  align?: 'left' | 'right' | 'center'
  /** Ancho mínimo en px */
  minWidth?: number
  /** Columna fija al hacer scroll horizontal */
  sticky?: boolean
}

export const BRAND_KPI_TOOLTIPS: Record<string, string> = {
  'Negocios abiertos':
    'Negocios de esta marca con estado abierto en HubSpot. Incluye toda la cartera activa, sin límite de antigüedad.',
  'Nuevos 7 días':
    'Negocios creados en los últimos 7 días calendario, de cualquier estado (abiertos, ganados o perdidos).',
  'Nuevos 30 días':
    'Negocios creados en los últimos 30 días calendario.',
  'Estancados +45d sin actividad':
    'Negocios abiertos sin ninguna actividad sincronizada en 45+ días, o sin actividad registrada en la ventana de sync (60 días).',
  'Cobertura llamadas':
    'Negocios activos con al menos una llamada en la ventana de contacto (21d) ÷ negocios activos de la marca.',
  'Cobertura WhatsApp':
    'Negocios activos con al menos un mensaje WhatsApp en la ventana de contacto ÷ negocios activos.',
  'Cobertura combinada':
    'Negocios activos contactados por llamada y/o WhatsApp en la ventana de contacto ÷ negocios activos.',
}

export const BRAND_ADVISOR_COLUMNS: MetricColumn[] = [
  {
    label: 'Asesor',
    tooltip: 'Propietario del negocio en HubSpot para esta marca. Un asesor en varias marcas aparece en cada pestaña por separado.',
  },
  {
    label: 'Abiertos',
    tooltip: 'Cantidad de negocios abiertos asignados a este asesor en la marca seleccionada.',
  },
  {
    label: 'Nuevos 7d',
    tooltip: 'Negocios asignados al asesor creados en los últimos 7 días.',
  },
  {
    label: 'Nuevos 30d',
    tooltip: 'Negocios asignados al asesor creados en los últimos 30 días.',
  },
  {
    label: 'Estanc. 45d',
    tooltip: 'Negocios abiertos del asesor sin actividad en 45+ días (según actividades sincronizadas).',
  },
  {
    label: 'Tareas hechas',
    tooltip: 'Total de tareas completadas vinculadas a sus negocios (ventana de actividades sincronizadas).',
  },
  {
    label: 'Tareas abiertas',
    tooltip: 'Tareas pendientes aún no completadas, asociadas a negocios del asesor.',
  },
  {
    label: 'Tareas vencidas',
    tooltip:
      'Cuenta cada tarea individual pendiente cuya fecha de vencimiento ya pasó. Si un negocio tiene 3 tareas vencidas, suma 3. Ejemplo: 20 = veinte tareas atrasadas en total.',
  },
  {
    label: 'Neg. c/ tareas venc.',
    tooltip:
      'Cuenta negocios distintos que tienen al menos una tarea vencida (cada negocio suma máximo 1). Ejemplo: 18 negocios con tareas atrasadas, aunque entre todos sumen 20 tareas.',
  },
  {
    label: 'Gestión 30d',
    tooltip: 'Porcentaje de negocios abiertos con al menos una actividad en los últimos 30 días (llamadas, mensajes, reuniones o notas en ventana sync).',
  },
  {
    label: 'Cob. llamadas',
    tooltip: 'Negocios activos con al menos una llamada en la ventana de contacto (21d por defecto) ÷ negocios activos del asesor.',
  },
  {
    label: 'Cob. WhatsApp',
    tooltip: 'Negocios activos con al menos un mensaje WhatsApp en la ventana de contacto ÷ negocios activos.',
  },
  {
    label: 'Cob. combinada',
    tooltip: 'Negocios activos contactados por llamada y/o WhatsApp en la ventana de contacto ÷ negocios activos.',
  },
  {
    label: 'Atrasados 21d',
    tooltip:
      'Negocios activos sin contacto en la ventana de contacto (21d). Incluye cualquier canal sincronizado.',
  },
  {
    label: 'Ventas totales',
    tooltip: 'Unidades vendidas (cierres ganados) históricas del asesor en esta marca.',
  },
  {
    label: 'Ventas este mes',
    tooltip: 'Cierres ganados en el mes calendario en curso, por fecha de cierre.',
  },
  {
    label: 'Cambio mensual',
    tooltip:
      'Compara unidades vendidas entre el mes calendario en curso y el mes anterior (por fecha de cierre). El badge indica ambos meses.',
  },
]

export const BRAND_ZONE_COLUMNS: MetricColumn[] = [
  { label: 'Marca', tooltip: 'Marca comercial del negocio (Voyah, MHero, Shacman).' },
  { label: 'Zona', tooltip: 'Zona territorial resuelta desde propiedades HubSpot o contacto asociado.' },
  { label: 'Total', tooltip: 'Todos los negocios en la combinación marca × zona con los filtros actuales.' },
  { label: 'Abiertos', tooltip: 'Negocios abiertos en esa marca y zona.' },
  { label: 'Pipeline', tooltip: 'Suma del valor (amount) de los negocios abiertos.' },
  {
    label: 'Gestión 30d',
    tooltip: '% de negocios abiertos con actividad registrada en los últimos 30 días.',
  },
  {
    label: 'Contacto 30d',
    tooltip: '% de negocios abiertos con contacto efectivo en 30 días (llamada, mensaje o reunión completada).',
  },
  {
    label: 'Desatendidos',
    tooltip: 'Negocios abiertos sin gestión reciente, sin contacto efectivo, con tareas vencidas o sin próxima tarea.',
  },
  {
    label: 'Tareas venc.',
    tooltip: 'Negocios con al menos una tarea vencida pendiente.',
  },
  {
    label: 'Tasa cierre',
    tooltip: 'Ganados ÷ (ganados + perdidos) en la población filtrada. Solo negocios cerrados.',
  },
]

export const FUNNEL_COLUMNS: MetricColumn[] = [
  { label: 'Etapa', tooltip: 'Etapa actual del negocio en HubSpot (población en el momento del análisis).' },
  { label: 'Total', tooltip: 'Negocios que están actualmente en esta etapa.' },
  { label: 'Abiertos', tooltip: 'De los anteriores, cuántos siguen abiertos.' },
  { label: 'Ganados', tooltip: 'Negocios en esta etapa clasificados como ganados.' },
  { label: 'Perdidos', tooltip: 'Negocios en esta etapa clasificados como perdidos.' },
  {
    label: 'Estancados',
    tooltip: 'Negocios abiertos en la etapa sin movimiento prolongado (sin actividad o mucho tiempo en etapa).',
  },
]

export const ADVISORS_COMPARE_COLUMNS: MetricColumn[] = [
  { label: 'Asesor', tooltip: 'Propietario HubSpot del negocio.' },
  { label: 'Cartera', tooltip: 'Total de negocios asignados al asesor en la población filtrada.' },
  { label: 'Abiertos', tooltip: 'Negocios abiertos del asesor.' },
  {
    label: 'Gestión 30d',
    tooltip: '% de la cartera abierta con actividad en los últimos 30 días.',
  },
  {
    label: 'Contacto 30d',
    tooltip: '% de la cartera abierta con contacto efectivo en 30 días.',
  },
  { label: 'Sin act. 30d', tooltip: 'Negocios abiertos sin actividad en 30 días.' },
  { label: 'Tareas venc.', tooltip: 'Negocios del asesor con tareas vencidas.' },
  { label: 'Desatendidos', tooltip: 'Negocios abiertos marcados como desatendidos.' },
  { label: 'Disciplina', tooltip: 'Índice compuesto: gestión, contacto, tareas y desatención (0–100).' },
  { label: 'Efectividad', tooltip: 'Índice basado en tasa de cierre y valor ganado (0–100).' },
  { label: 'Estado', tooltip: 'Gestión saludable, requiere seguimiento, cartera en riesgo o información insuficiente.' },
  { label: 'Tasa cierre', tooltip: 'Ganados ÷ (ganados + perdidos) del asesor.' },
]

export const ADVISOR_DEAL_COLUMNS: MetricColumn[] = [
  { label: 'Negocio', tooltip: 'Nombre del negocio en HubSpot.' },
  { label: 'Estado', tooltip: 'Abierto, ganado o perdido según HubSpot.' },
  { label: 'Grupo etapa', tooltip: 'Agrupación comercial de la etapa (prospección, cotización, venta, etc.).' },
  { label: 'Etapa', tooltip: 'Etapa actual del pipeline en HubSpot.' },
  { label: 'Valor', tooltip: 'Monto del negocio (amount).' },
  { label: 'Días sin act.', tooltip: 'Días desde la última actividad sincronizada.' },
  { label: 'Días sin contacto', tooltip: 'Días desde el último contacto efectivo.' },
  { label: 'Tareas venc.', tooltip: 'Cantidad de tareas vencidas pendientes.' },
  { label: 'Señales', tooltip: 'Estancado 45d, desatendido o con tareas vencidas.' },
]

export const ADVISOR_TASK_COLUMNS: MetricColumn[] = [
  { label: 'Tarea', tooltip: 'Asunto de la tarea en HubSpot.' },
  { label: 'Contacto', tooltip: 'Contacto asociado a la tarea en HubSpot.' },
  { label: 'Negocio', tooltip: 'Negocio asociado a la tarea.' },
  { label: 'Etapa negocio', tooltip: 'Etapa del negocio vinculado. Si solo hay contacto, no aplica etapa de pipeline.' },
  { label: 'Estado', tooltip: 'Pendiente o completada.' },
  { label: 'Prioridad', tooltip: 'Prioridad configurada en HubSpot.' },
  { label: 'Vence', tooltip: 'Fecha de vencimiento de la tarea.' },
  {
    label: 'Días sin resolver',
    tooltip: 'Días desde el vencimiento. Aplica a pendientes vencidas y completadas que se cerraron tarde.',
  },
]

export const EXPLORER_COLUMNS: MetricColumn[] = [
  { label: 'Negocio', tooltip: 'Nombre del negocio en HubSpot.' },
  { label: 'Marca', tooltip: 'Marca comercial asignada al negocio.' },
  { label: 'Zona', tooltip: 'Zona territorial del negocio.' },
  { label: 'Etapa', tooltip: 'Etapa actual del pipeline.' },
  { label: 'Asesor', tooltip: 'Propietario asignado en HubSpot.' },
  { label: 'Valor', tooltip: 'Monto del negocio (amount).' },
  {
    label: 'Días sin act.',
    tooltip: 'Días desde la última actividad sincronizada (ventana 60 días).',
  },
  {
    label: 'Días sin contacto',
    tooltip: 'Días desde el último contacto efectivo (llamada, mensaje o reunión completada).',
  },
  { label: 'Tareas venc.', tooltip: 'Cantidad de tareas vencidas pendientes en el negocio.' },
  {
    label: 'Alerta',
    tooltip: 'Motivo de riesgo: desatendido, estancado o combinación de señales.',
  },
]

export function normalizeColumns(
  columns: Array<string | MetricColumn>,
): MetricColumn[] {
  return columns.map((col) =>
    typeof col === 'string' ? { label: col, tooltip: `Métrica: ${col}` } : col,
  )
}
