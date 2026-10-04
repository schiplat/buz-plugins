export interface StepInput {
  name: string
  type?: string
  required?: boolean
  default?: string | null
  masking?: boolean
  description?: string | null
}

export interface StepTemplate {
  id: string
  version: string
  file: string
  name?: string | null
  description?: string | null
  description_zh?: string | null
  [key: string]: unknown
  author?: string | null
  author_url?: string | null
  source_repo?: string | null
  license?: string | null
  publisher?: string
  engine: string
  keywords?: string[] | null
  default_timeout?: string | null
  requires_buz?: string | null
  buz_compatible?: boolean
  content_sha256: string
  inputs: StepInput[]
}

export interface StepLibrary {
  templates: StepTemplate[]
  unparseable?: { file: string; error: string }[]
  generated_at?: string
}

export const REPO_URL = 'https://github.com/schiplat/buz-plugins'

export function reportUrl(t: StepTemplate) {
  return `${REPO_URL}/issues/new?template=report.yml&title=${encodeURIComponent(`[report] ${t.id}@${t.version}`)}`
}
