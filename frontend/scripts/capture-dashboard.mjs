import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.resolve(__dirname, '../../docs/captures')

await mkdir(outDir, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage()

await page.setViewportSize({ width: 1440, height: 900 })
await page.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded', timeout: 120000 })

await page.waitForSelector('text=Resumen semanal comercial', { timeout: 30000 })
await page.waitForSelector('text=Leads creados', { timeout: 180000 })
await page.waitForTimeout(2000)

await page.screenshot({ path: path.join(outDir, 'dashboard-desktop.png'), fullPage: true })

await page.setViewportSize({ width: 390, height: 844 })
await page.waitForTimeout(1500)
await page.screenshot({ path: path.join(outDir, 'dashboard-mobile.png'), fullPage: true })

await browser.close()
console.log('Capturas guardadas en', outDir)
