<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ExternalLink,
  Loader2,
  Search,
  ShieldAlert,
  Store,
  TriangleAlert,
} from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import Pagination from '@/components/ui/Pagination.vue'
import Select from '@/components/ui/Select.vue'
import Dialog from '@/components/ui/Dialog.vue'
import TemplateCard from '@/components/TemplateCard.vue'
import TemplateDetail from '@/components/TemplateDetail.vue'
import { detectLanguage, I18N, LOCALE_NAMES, type Messages } from '@/i18n'
import type { StepLibrary, StepTemplate } from '@/types'
import { REPO_URL } from '@/types'

const SUPPORTED = Object.keys(LOCALE_NAMES)
const lang = ref(detectLanguage(SUPPORTED))
const messages = computed<Messages>(() => I18N[lang.value] ?? I18N.en!)
const t = (key: keyof Messages & string, ...args: unknown[]) => {
  const value = messages.value[key] ?? I18N.en![key] ?? key
  return typeof value === 'function' ? (value as (a: unknown) => string)(args[0]) : value
}

const library = ref<StepLibrary>({ templates: [] })
const loading = ref(true)
const error = ref('')
const search = ref('')
const publisherFilter = ref('all')
const page = ref(1)
const PAGE_SIZE = 6
const selected = ref<StepTemplate | null>(null)
const detailOpen = ref(false)

function localized(t: StepTemplate): string {
  const key = lang.value === 'en' ? 'description' : `description_${lang.value}`
  return (t[key] as string) || t.description || t.description_zh || ''
}

const filtered = computed(() => {
  let list = library.value.templates.slice()
  if (publisherFilter.value !== 'all')
    list = list.filter((t) => (t.publisher || 'community') === publisherFilter.value)
  const q = search.value.trim().toLowerCase()
  if (q)
    list = list.filter((t) => {
      const haystack = [
        t.id, t.name, t.description, t.description_zh, t.author, t.engine, ...(t.keywords || []),
      ].filter(Boolean).join(' ').toLowerCase()
      return haystack.includes(q)
    })
  return list.sort((a, b) => a.id.localeCompare(b.id) || b.version.localeCompare(a.version))
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paged = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filtered.value.slice(start, start + PAGE_SIZE)
})

watch([search, publisherFilter], () => (page.value = 1))
watch(lang, () => (page.value = 1))

function localizedDescription(t: StepTemplate): string {
  const key = lang.value === 'en' ? 'description' : `description_${lang.value}`
  return (t[key] as string) || t.description || t.description_zh || ''
}

function reviewedBadge(t: StepTemplate): string {
  return t.reviewed
    ? `<span class="badge reviewed" title="${messages.value.reviewedTip}${t.reviewed_at ? ` (${t.reviewed_at})` : ''}">✓ ${messages.value.reviewed}</span>`
    : `<span class="badge unreviewed" title="${messages.value.unreviewedTip}">${messages.value.unreviewed}</span>`
}

function publisherBadge(t: StepTemplate): string {
  const publisher = t.publisher || 'community'
  const label = publisher === 'official' ? t('official') : t('community')
  return `<span class="badge ${publisher === 'official' ? 'official' : 'community'}">${label}</span>`
}

function usageSnippet(t: StepTemplate): string {
  const lines = [`- name: ${t.id.split('/').pop()}`, `  uses: ${t.id}@${t.version}`]
  const required = t.inputs.filter((i) => i.required)
  if (required.length) {
    lines.push('  with:')
    for (const input of required) lines.push(`    ${input.name}: `)
  }
  return lines.join('\n')
}

const reportUrl = (t: StepTemplate) => `${REPO_URL}/issues/new?template=report.yml&title=${encodeURIComponent(`[report] ${t.id}@${t.version}`)}`

onMounted(async () => {
  try {
    const resp = await fetch('site-data.json')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    library.value = (await resp.json()) as StepLibrary
  } catch (e) {
    error.value = `${e}`
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="min-h-screen">
    <!-- Header -->
    <header class="border-b bg-card">
      <div class="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-4 px-6 py-6">
        <div>
          <div class="flex items-center gap-2">
            <Store class="h-5 w-5 text-primary" />
            <h1 class="text-xl font-semibold tracking-tight">Buz Plugins Marketplace</h1>
          </div>
          <p class="mt-1 max-w-2xl text-sm text-muted-foreground">{{ t('tagline') }}</p>
        </div>
        <div class="flex items-center gap-2">
          <Select v-model="lang" class="w-28" aria-label="Language / 语言">
            <option v-for="(name, code) in LOCALE_NAMES" :key="code" :value="code">{{ name }}</option>
          </Select>
          <Button variant="outline" as="a" :href="`${REPO_URL}`" target="_blank">
            <ExternalLink class="mr-1 h-3.5 w-3.5" /> GitHub
          </Button>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-6xl px-6 pb-16">
      <!-- Error banner -->
      <div v-if="error" class="mt-6 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        {{ t('loadFail') }}: {{ error }}
      </div>

      <!-- Unparseable warning -->
      <div v-if="library.unparseable?.length" class="mt-6 rounded-lg border border-amber-600/30 bg-amber-600/10 p-4 text-xs text-amber-700 dark:text-amber-500">
        <div class="mb-1 flex items-center gap-1.5 font-semibold">
          <TriangleAlert class="h-3.5 w-3.5" />
          {{ library.unparseable.length }} file(s) failed to parse
        </div>
        <div v-for="u in library.unparseable" :key="u.file" class="font-mono">{{ u.file }} — {{ u.error }}</div>
      </div>

      <!-- Toolbar -->
      <div class="mt-6 flex flex-wrap items-center gap-3">
        <div class="relative min-w-[16rem] flex-1">
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input v-model="search" :placeholder="t('search')" class="pl-9" />
        </div>
        <Select v-model="publisherFilter" class="w-44">
          <option value="all">{{ t('all') }}</option>
          <option value="official">{{ t('official') }}</option>
          <option value="community">{{ t('community') }}</option>
        </Select>
      </div>

      <!-- Content -->
      <div v-if="loading" class="flex items-center justify-center py-20 text-muted-foreground">
        <Loader2 class="mr-2 h-5 w-5 animate-spin" /> Loading…
      </div>

      <template v-else>
        <div class="mt-4 text-xs text-muted-foreground">{{ t('templatesCount', filtered.length) }}</div>

        <div v-if="!filtered.length" class="py-20 text-center text-sm text-muted-foreground">
          {{ search.trim() || publisherFilter !== 'all' ? t('emptySearch') : t('empty') }}
        </div>

        <div v-else class="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card
            v-for="tmpl in paged"
            :key="`${tmpl.id}@${tmpl.version}`"
            class="group flex cursor-pointer flex-col p-5 transition-shadow hover:shadow-md"
            @click="selected = tmpl; detailOpen = true"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="truncate font-semibold">{{ tmpl.name || tmpl.id }}</div>
                <div class="mt-0.5 font-mono text-xs text-muted-foreground">{{ tmpl.id }} · v{{ tmpl.version }}</div>
              </div>
              <div class="flex shrink-0 flex-col items-end gap-1">
                <Badge :variant="tmpl.reviewed ? 'reviewed' : 'unreviewed'" :title="tmpl.reviewed ? t('reviewedTip') : t('unreviewedTip')">
                  {{ tmpl.reviewed ? `✓ ${t('reviewed')}` : t('unreviewed') }}
                </Badge>
                <Badge :variant="(tmpl.publisher || 'community') === 'official' ? 'official' : 'community'">
                  {{ (tmpl.publisher || 'community') === 'official' ? t('official') : t('community') }}
                </Badge>
              </div>
            </div>

            <p class="mt-3 line-clamp-3 flex-1 text-sm text-muted-foreground">{{ localized(tmpl) }}</p>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <Badge variant="secondary" class="font-mono">{{ tmpl.engine }}</Badge>
              <Badge v-if="tmpl.default_timeout" variant="secondary" class="font-mono">{{ tmpl.default_timeout }}</Badge>
              <Badge variant="secondary">{{ t('inputsCount', tmpl.inputs.length) }}</Badge>
              <Badge v-if="tmpl.buz_compatible === false" variant="warn">
                <ShieldAlert class="mr-0.5 h-3 w-3" />{{ t('incompatible') }}
              </Badge>
            </div>

            <div class="mt-4 flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
              <span class="truncate">{{ tmpl.author ? `${t('by')} ${tmpl.author}` : '' }}</span>
              <span class="inline-flex items-center gap-1 font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                {{ t('details') }} →
              </span>
            </div>
          </Card>
        </div>

        <div class="mt-8 flex items-center justify-between gap-4">
          <span class="text-xs text-muted-foreground">{{ t('page') }} {{ page }} {{ t('of') }} {{ totalPages }}</span>
          <Pagination :page="page" :total-pages="totalPages" @update:page="page = $event">
            <template #prev>{{ t('prev') }}</template>
            <template #next>{{ t('next') }}</template>
          </Pagination>
        </div>
      </template>
    </main>

    <footer class="border-t bg-card">
      <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-6 py-5 text-xs text-muted-foreground">
        <span>
          <a :href="REPO_URL" target="_blank" rel="noopener" class="hover:text-foreground">{{ REPO_URL.replace('https://', '') }}</a>
          · <a :href="`${REPO_URL}/issues/new?template=report.yml`" target="_blank" rel="noopener" class="hover:text-foreground">{{ t('report') }}</a>
          · <span>{{ t('securityNote') }}</span>
        </span>
        <span class="font-mono text-[10px]">Index generated at {{ library.generated_at || '' }}</span>
      </div>
    </footer>

    <!-- Detail dialog -->
    <Dialog v-model="detailOpen">
      <div v-if="selected">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="font-mono text-sm font-semibold">{{ selected.id }}@{{ selected.version }}</div>
            <div class="mt-1.5 flex flex-wrap gap-1.5">
              <Badge :variant="selected.reviewed ? 'reviewed' : 'unreviewed'"
                :title="selected.reviewed ? t('reviewedTip') : t('unreviewedTip')">
                {{ selected.reviewed ? `✓ ${t('reviewed')}` : t('unreviewed') }}
              </Badge>
              <Badge :variant="(selected.publisher || 'community') === 'official' ? 'official' : 'community'">
                {{ (selected.publisher || 'community') === 'official' ? t('official') : t('community') }}
              </Badge>
            </div>
          </div>
          <Button variant="ghost" size="sm" @click="detailOpen = false">✕</Button>
        </div>

        <p class="mt-4 text-sm">{{ localized(selected) }}</p>

        <div class="mt-4 flex flex-wrap gap-1.5">
          <Badge variant="secondary" class="font-mono">{{ selected.engine }}</Badge>
          <Badge v-if="selected.default_timeout" variant="secondary">{{ t('timeout') }}: {{ selected.default_timeout }}</Badge>
          <Badge v-if="selected.license" variant="secondary">{{ selected.license }}</Badge>
          <Badge v-if="selected.author" variant="secondary">{{ t('by') }} {{ selected.author }}</Badge>
        </div>

        <h3 class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ t('usage') }}</h3>
        <pre class="overflow-x-auto rounded-md border bg-muted/60 p-3 font-mono text-xs">{{ usageSnippet(selected) }}</pre>

        <template v-if="selected.inputs.length">
          <h3 class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ t('inputs') }}</h3>
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b text-left text-muted-foreground">
                <th class="py-1.5 pr-3 font-medium">{{ t('name') }}</th>
                <th class="py-1.5 pr-3 font-medium">{{ t('type') }}</th>
                <th class="py-1.5 pr-3 font-medium">{{ t('required') }}</th>
                <th class="py-1.5 pr-3 font-medium">{{ t('masking') }}</th>
                <th class="py-1.5 font-medium">{{ t('description') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="input in selected.inputs" :key="input.name" class="border-b last:border-0">
                <td class="py-1.5 pr-3 font-mono">{{ input.name }}</td>
                <td class="py-1.5 pr-3">{{ input.type || 'string' }}</td>
                <td class="py-1.5 pr-3">{{ input.required ? t('yes') : t('no') }}</td>
                <td class="py-1.5 pr-3">{{ input.masking ? t('yes') : t('no') }}</td>
                <td class="py-1.5 text-muted-foreground">{{ input.description || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <h3 class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ t('integrity') }}</h3>
        <p class="font-mono text-xs text-muted-foreground">sha256: {{ selected.content_sha256 }}</p>
        <p class="mt-1 text-xs text-muted-foreground">{{ t('pinHint') }}</p>

        <div class="mt-5 flex flex-wrap items-center gap-3 border-t pt-4 text-xs">
          <a :href="reportUrl(selected)" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-destructive hover:underline">
            <ShieldAlert class="h-3.5 w-3.5" /> {{ t('reportHint') }}
          </a>
          <a v-if="selected.source_repo" :href="selected.source_repo" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-primary hover:underline">
            <ExternalLink class="h-3.5 w-3.5" /> {{ t('sourceRepo') }}
          </a>
        </div>
      </div>
    </Dialog>
  </div>
</template>
