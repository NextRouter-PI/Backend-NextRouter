#!/usr/bin/env node
/**
 * Ponto de entrada do backend para o teste de arquivos estáticos e SPA.
 * Executa o runner em frontend/scripts/test_static_serving.mjs.
 */
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = fileURLToPath(new URL('.', import.meta.url))
const frontendScript = resolve(scriptDir, '../../frontend/scripts/test_static_serving.mjs')

const { main } = await import(frontendScript)
await main()
