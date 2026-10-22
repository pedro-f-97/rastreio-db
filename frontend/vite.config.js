import { execSync } from 'node:child_process'
import process from 'node:process'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// A versão que a página Conceitos mostra (achado 10.3): a variável VERSAO, se
// existir; na CI, a tag que disparou o build (o checkout não traz as tags); em
// local, o `git describe` (ex. v0.2.8-187-g75d261b); e "dev" sem git.
function versao() {
  if (process.env.VERSAO) return process.env.VERSAO
  if (process.env.GITHUB_REF_TYPE === 'tag') return process.env.GITHUB_REF_NAME
  try {
    return execSync('git describe --tags --always --dirty', { encoding: 'utf-8' }).trim()
  } catch {
    return 'dev'
  }
}

export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_VERSAO': JSON.stringify(versao()),
  },
  server: {
    port: 9743,
    proxy: {
      '/api': 'http://localhost:9742',
    },
  },
})
