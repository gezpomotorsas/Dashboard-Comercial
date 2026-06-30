# Ejecutable Windows — Dashboard Comercial

## Qué obtienes

- **`DashboardComercial.exe`**: abre el dashboard en el navegador (puerto **8765** por defecto).
- **`runtime/`**: código de la app (se actualiza desde GitHub).
- **`data/.env`**: credenciales HubSpot + Supabase (no se sobrescriben al actualizar).

## Construir el ejecutable (en tu PC con Python)

Cierra **DashboardComercial.exe** antes de compilar (si no, PyInstaller no puede borrar `dist/`).

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows-exe.ps1
```

Permanente (opcional): `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Salida para compartir:

```text
dist/DashboardComercial/
  DashboardComercial.exe
  runtime/
  data/
  .env.example
```

Comprime esa carpeta en ZIP y compártela.

## Primera ejecución (usuario final)

1. Descomprime la carpeta.
2. Edita **`data\.env`** (no el `.env` de la carpeta raíz) con HubSpot y Supabase.
   - Se crea automáticamente la primera vez; si ya tienes un `.env` configurado en la raíz, se copia desde ahí.
   - Si ves error **503**, casi siempre es porque `data\.env` está vacío o incompleto.
3. Doble clic en **`DashboardComercial.exe`**.
4. Se abre `http://127.0.0.1:8765/`.

## Actualizar desde GitHub

### Automático al abrir

Por defecto `AUTO_UPDATE_ON_START=true`: al iniciar el .exe comprueba si hay una **release nueva** en GitHub y descarga `runtime.zip`.

### Botón manual

Abre en el navegador:

```text
http://127.0.0.1:8765/actualizar
```

1. **Comprobar** — consulta GitHub.
2. **Descargar actualización** — baja `runtime.zip` de la última release.
3. **Reiniciar ahora** — aplica y reinicia el servicio.

### Cuándo se publica una release

Cada **push a `main`** ejecuta el workflow `.github/workflows/release-windows.yml` y publica:

- `runtime.zip` (app + frontend compilado)
- `DashboardComercial.exe`

La release incluye en la descripción `commit: <sha>` para que el launcher sepa si hay versión nueva.

## Variables opcionales (`data\.env`)

Repositorio: [gezpomotorsas/Dashboard-Comercial](https://github.com/gezpomotorsas/Dashboard-Comercial)

```env
GITHUB_REPO=gezpomotorsas/Dashboard-Comercial
# Obligatorio si el repo es privado (PAT con lectura de Contents / repo)
GITHUB_TOKEN=ghp_xxxxxxxx
AUTO_UPDATE_ON_START=true
UPDATE_SOURCE=release    # release | git
OPEN_BROWSER=true
DASHBOARD_PORT=8765
```

### Primera vez: publicar una release en GitHub

1. Haz push a `main` (dispara el workflow `Release Windows runtime`).
2. En GitHub → **Releases** debe aparecer `runtime.zip` + `DashboardComercial.exe`.
3. En cada servidor, pon `GITHUB_TOKEN` en `data\.env` si el repo es privado.
4. Usa el botón **Actualizar app** o `http://127.0.0.1:8765/actualizar`.

## Línea de comandos

```powershell
DashboardComercial.exe --check-update
DashboardComercial.exe --apply-update
```

## Notas

- El .exe **no requiere Python instalado** en el PC destino.
- Antivirus pueden marcar PyInstaller; firma digital del exe reduce falsos positivos.
- Para Cloudflare Tunnel, apunta el hostname a `http://127.0.0.1:8765`.

## Si el navegador muestra error MIME en `/assets/*.js`

Significa que faltan los archivos compilados del frontend en `runtime/frontend/dist/assets/`. Vuelve a generar el paquete:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-runtime.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows-exe.ps1
```

Comparte de nuevo la carpeta `dist/DashboardComercial` completa.
