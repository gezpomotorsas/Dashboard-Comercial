import { useEffect, useState } from 'react'

export function SlowLoadNotice({
  title = 'Cargando datos…',
  hint = 'La primera carga calcula llamadas y WhatsApp sobre toda la cartera. Puede tardar hasta 1 minuto.',
}: {
  title?: string
  hint?: string
}) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => window.clearInterval(id)
  }, [])

  return (
    <section className="rounded-xl border bg-white p-8 text-center shadow-sm">
      <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" />
      <p className="font-medium text-slate-800">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{hint}</p>
      <p className="mt-3 text-xs text-slate-400">{seconds}s</p>
    </section>
  )
}
