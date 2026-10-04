<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Check,
  Copy,
  ExternalLink,
  Loader2,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Store,
  TriangleAlert,
} from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import Pagination from '@/components/ui/Pagination.vue'
import Dialog from '@/components/ui/Dialog.vue'
import FiltersSidebar from '@/components/FiltersSidebar.vue'
import { copyText } from '@/lib/clipboard'
import { T } from '@/ui-text'
import type { StepLibrary, StepTemplate } from '@/types'
import { REPO_URL } from '@/types'

const library = ref<StepLibrary>({ templates: [], unparseable: [] })
const loading = ref(true)
const error = ref('')
const search = ref('')
const publisher = ref('all')
const engine = ref('all')
const review = ref('all')
const selectedKeywords = ref<string[]>([])
const page = ref(1)
const PAGE_SIZE = 6
const showMobileFilters = ref(false)
const selected = ref<StepTemplate | null>(null)
const detailOpen = ref(false)
const copiedCard = ref<string | null>(null)
const copiedUsage = ref(false)

async function copyUsesRef(t: StepTemplate) {
  if (await copyText(`${t.id}@${t.version}`)) {
    copiedCard.value = `${t.id}@${t.version}`
    setTimeout(() => {
      if (copiedCard.value === `${t.id}@${t.version}`) copiedCard.value = null
    }, 1500)
  }
}

async function copyUsage(t: StepTemplate) {
  if (await copyText(usageSnippet(t))) {
    copiedUsage.value = true
    setTimeout(() => (copiedUsage.value = false), 1500)
  }
}

function localized(t: StepTemplate): string {
  return t.description || t.description_zh || ''
}

const allTemplates = computed(() => library.value.templates)

const publisherFacets = computed(() => countBy(allTemplates.value, (t) => t.publisher || 'community'))
const engineFacets = computed(() => countBy(allTemplates.value, (t) => t.engine))
const keywordFacets = computed(() => {
  const counts = new Map<string, number>()
  for (const t of allTemplates.value)
    for (const keyword of t.keywords || []) counts.set(keyword, (counts.get(keyword) || 0) + 1)
  return [...counts.entries()]
    .map(([value, count]) => ({ value, label: value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
})

const reviewFacets = computed(() => {
  const reviewed = allTemplates.value.filter((t) => t.reviewed).length
  return [
    { value: 'all', label: T.all, count: allTemplates.value.length },
    { value: 'reviewed', label: T.reviewed, count: reviewed },
    { value: 'unreviewed', label: T.unreviewed, count: allTemplates.value.length - reviewed },
  ]
})

function countBy(items: StepTemplate[], key: (t: StepTemplate) => string) {
  const counts = new Map<string, number>()
  for (const item of items) {
    const value = key(item) || 'unknown'
    counts.set(value, (counts.get(value) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, label: value, count }))
    .sort((a, b) => a.value.localeCompare(b.value))
}

const hasActiveFilters = computed(
  () =>
    publisher.value !== 'all' ||
    engine.value !== 'all' ||
    review.value !== 'all' ||
    selectedKeywords.value.length > 0 ||
    search.value.trim() !== '',
)

function clearFilters() {
  publisher.value = 'all'
  engine.value = 'all'
  review.value = 'all'
  selectedKeywords.value = []
  search.value = ''
}

const filtered = computed(() => {
  let list = allTemplates.value.slice()
  if (publisher.value !== 'all')
    list = list.filter((t) => (t.publisher || 'community') === publisher.value)
  if (engine.value !== 'all') list = list.filter((t) => t.engine === engine.value)
  if (review.value !== 'all')
    list = list.filter((t) => (review.value === 'reviewed' ? t.reviewed : !t.reviewed))
  if (selectedKeywords.value.length)
    list = list.filter((t) =>
      selectedKeywords.value.some((keyword) => (t.keywords || []).includes(keyword)),
    )
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

watch([search, publisher, engine, review, selectedKeywords], () => (page.value = 1))

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
  <div class="flex min-h-screen flex-col">
    <!-- Header -->
    <header class="border-b bg-card">
      <div class="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-4">
        <a href="#" class="flex items-center gap-2">
          <Store class="h-5 w-5 text-primary" />
          <span class="text-lg font-semibold tracking-tight">Buz Plugins Marketplace</span>
        </a>
        <div class="flex items-center gap-2">
          <a :href="`${REPO_URL}/issues/new?template=report.yml`" target="_blank" rel="noopener" class="hidden text-xs text-muted-foreground hover:text-foreground sm:inline">
            {{ T.report }}
          </a>
          <Button variant="outline" size="sm" as="a" :href="REPO_URL" target="_blank">
            GitHub <ExternalLink class="ml-1 h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </header>

    <div class="mx-auto flex w-full max-w-7xl flex-1 gap-8 px-6">
      <!-- Sidebar filters (desktop) -->
      <aside class="hidden w-56 shrink-0 border-r py-6 pr-6 lg:block">
        <div class="sticky top-6">
          <FiltersSidebar
            :publisher="publisher"
            :engine="engine"
            :review="review"
            :selected-keywords="selectedKeywords"
            :publisher-facets="publisherFacets"
            :engine-facets="engineFacets"
            :review-facets="reviewFacets"
            :keyword-facets="keywordFacets"
            :has-active-filters="hasActiveFilters"
            @update:publisher="publisher = $event"
            @update:engine="engine = $event"
            @update:review="review = $event"
            @update:selected-keywords="selectedKeywords = $event"
            @clear="clearFilters()"
          />
        </div>
      </aside>

      <!-- Main -->
      <main class="min-w-0 flex-1 py-6">
        <div v-if="error" class="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {{ T.loadFail }}: {{ error }}
        </div>

        <div v-if="library.unparseable?.length" class="mb-4 rounded-lg border border-amber-600/30 bg-amber-600/10 p-3 text-xs text-amber-700 dark:text-amber-500">
          <div class="mb-1 flex items-center gap-1.5 font-semibold">
            <TriangleAlert class="h-3.5 w-3.5" />
            {{ library.unparseable.length }} file(s) failed to parse — run buz-manager step-validate for details
          </div>
          <div v-for="u in library.unparseable" :key="u.file" class="font-mono">{{ u.file }} — {{ u.error }}</div>
        </div>

        <!-- Toolbar -->
        <div class="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" class="lg:hidden" @click="showMobileFilters = !showMobileFilters">
            <SlidersHorizontal class="mr-1 h-3.5 w-3.5" /> {{ T.filters }}
          </Button>
          <div class="relative min-w-[14rem] flex-1">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="search" :placeholder="T.search" class="pl-9" />
          </div>
          <span class="ml-auto text-xs text-muted-foreground">{{ T.templatesCount(filtered.length) }}</span>
        </div>

        <!-- Mobile filter panel -->
        <div v-if="showMobileFilters" class="mt-3 rounded-lg border bg-card p-4 lg:hidden">
          <FiltersSidebar
            :publisher="publisher"
            :engine="engine"
            :review="review"
            :selected-keywords="selectedKeywords"
            :publisher-facets="publisherFacets"
            :engine-facets="engineFacets"
            :review-facets="reviewFacets"
            :keyword-facets="keywordFacets"
            :has-active-filters="hasActiveFilters"
            @update:publisher="publisher = $event"
            @update:engine="engine = $event"
            @update:review="review = $event"
            @update:selected-keywords="selectedKeywords = $event"
            @clear="clearFilters(); showMobileFilters = false"
          />
        </div>

        <!-- Content -->
        <div v-if="loading" class="flex items-center justify-center py-20 text-muted-foreground">
          <Loader2 class="mr-2 h-5 w-5 animate-spin" /> Loading…
        </div>

        <template v-else>
          <div v-if="!filtered.length" class="py-20 text-center text-sm text-muted-foreground">
            {{ hasActiveFilters || search.trim() ? T.emptySearch : T.empty }}
          </div>

          <div v-else class="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Card
              v-for="tmpl in paged"
              :key="`${tmpl.id}@${tmpl.version}`"
              class="group flex cursor-pointer flex-col p-5 transition-shadow hover:shadow-md"
              @click="selected = tmpl; detailOpen = true"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="truncate font-semibold">{{ tmpl.name || tmpl.id }}</div>
                  <div class="mt-0.5 flex items-center gap-1">
                  <span class="truncate font-mono text-xs text-muted-foreground">{{ tmpl.id }} · v{{ tmpl.version }}</span>
                  <button
                    class="copy-btn inline-flex h-5 w-5 items-center justify-center rounded border border-transparent text-muted-foreground transition-colors hover:border-border hover:text-foreground"
                    :title="copiedCard === `${tmpl.id}@${tmpl.version}` ? T.copied : T.copy"
                    :aria-label="`${T.copy}: ${tmpl.id}@${tmpl.version}`"
                    @click.stop="copyUsesRef(tmpl)"
                  >
                    <Check v-if="copiedCard === `${tmpl.id}@${tmpl.version}`" class="h-3 w-3 text-emerald-600" />
                    <Copy v-else class="h-3 w-3" />
                  </button>
                </div>
                </div>
                <div class="flex shrink-0 flex-col items-end gap-1">
                  <Badge :variant="tmpl.reviewed ? 'reviewed' : 'unreviewed'" :title="tmpl.reviewed ? T.reviewedTip : T.unreviewedTip">
                    {{ tmpl.reviewed ? `✓ ${T.reviewed}` : T.unreviewed }}
                  </Badge>
                  <Badge :variant="(tmpl.publisher || 'community') === 'official' ? 'official' : 'community'">
                    {{ (tmpl.publisher || 'community') === 'official' ? T.official : T.community }}
                  </Badge>
                </div>
              </div>

              <p class="mt-3 line-clamp-3 flex-1 text-sm text-muted-foreground">{{ localized(tmpl) }}</p>

              <div class="mt-3 flex flex-wrap gap-1.5">
                <Badge variant="secondary" class="font-mono">{{ tmpl.engine }}</Badge>
                <Badge v-if="tmpl.default_timeout" variant="secondary" class="font-mono">{{ tmpl.default_timeout }}</Badge>
                <Badge variant="secondary">{{ T.inputsCount(tmpl.inputs.length) }}</Badge>
                <Badge v-if="tmpl.buz_compatible === false" variant="warn">
                  <ShieldAlert class="mr-0.5 h-3 w-3" /> {{ T.incompatible }}
                </Badge>
              </div>

              <div class="mt-4 flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
                <span class="truncate">{{ tmpl.author ? `${T.by} ${tmpl.author}` : '' }}</span>
                <span class="inline-flex items-center gap-1 font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  {{ T.details }} →
                </span>
              </div>
            </Card>
          </div>

          <div class="mt-8 flex items-center justify-between gap-4">
            <span class="text-xs text-muted-foreground">{{ T.page }} {{ page }} {{ T.of }} {{ totalPages }}</span>
            <Pagination :page="page" :total-pages="totalPages" @update:page="page = $event">
              <template #prev>{{ T.prev }}</template>
              <template #next>{{ T.next }}</template>
            </Pagination>
          </div>
        </template>
      </main>
    </div>

    <footer class="border-t bg-card">
      <div class="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-2 px-6 py-5 text-xs text-muted-foreground">
        <span>
          <a :href="REPO_URL" target="_blank" rel="noopener" class="hover:text-foreground">{{ REPO_URL.replace('https://', '') }}</a>
          · <a :href="`${REPO_URL}/issues/new?template=report.yml`" target="_blank" rel="noopener" class="hover:text-foreground">{{ T.report }}</a>
          · {{ T.securityNote }}
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
                :title="selected.reviewed ? T.reviewedTip : T.unreviewedTip">
                {{ selected.reviewed ? `✓ ${T.reviewed}` : T.unreviewed }}
              </Badge>
              <Badge :variant="(selected.publisher || 'community') === 'official' ? 'official' : 'community'">
                {{ (selected.publisher || 'community') === 'official' ? T.official : T.community }}
              </Badge>
            </div>
          </div>
          <Button variant="ghost" size="sm" @click="detailOpen = false">✕</Button>
        </div>

        <p class="mt-4 text-sm">{{ localized(selected) }}</p>

        <div class="mt-4 flex flex-wrap gap-1.5">
          <Badge variant="secondary" class="font-mono">{{ selected.engine }}</Badge>
          <Badge v-if="selected.default_timeout" variant="secondary">{{ T.timeout }}: {{ selected.default_timeout }}</Badge>
          <Badge v-if="selected.license" variant="secondary">{{ selected.license }}</Badge>
          <Badge v-if="selected.author" variant="secondary">{{ T.by }} {{ selected.author }}</Badge>
        </div>

        <h3 class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.usage }}</h3>
        <div class="relative">
          <pre class="overflow-x-auto rounded-md border bg-muted/60 p-3 pr-10 font-mono text-xs">{{ usageSnippet(selected) }}</pre>
          <button
            class="copy-btn absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-md border bg-background text-muted-foreground transition-colors hover:text-foreground"
            :title="copiedUsage ? T.copied : T.copy"
            aria-label="Copy usage snippet"
            @click="copyUsage(selected)"
          >
            <Check v-if="copiedUsage" class="h-3.5 w-3.5 text-emerald-600" />
            <Copy v-else class="h-3.5 w-3.5" />
          </button>
        </div>

        <template v-if="selected.inputs.length">
          <h3 class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.inputs }}</h3>
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b text-left text-muted-foreground">
                <th class="py-1.5 pr-3 font-medium">{{ T.name }}</th>
                <th class="py-1.5 pr-3 font-medium">{{ T.type }}</th>
                <th class="py-1.5 pr-3 font-medium">{{ T.required }}</th>
                <th class="py-1.5 pr-3 font-medium">{{ T.masking }}</th>
                <th class="py-1.5 font-medium">{{ T.description }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="input in selected.inputs" :key="input.name" class="border-b last:border-0">
                <td class="py-1.5 pr-3 font-mono">{{ input.name }}</td>
                <td class="py-1.5 pr-3">{{ input.type || 'string' }}</td>
                <td class="py-1.5 pr-3">{{ input.required ? T.yes : T.no }}</td>
                <td class="py-1.5 pr-3">{{ input.masking ? T.yes : T.no }}</td>
                <td class="py-1.5 text-muted-foreground">{{ input.description || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <h3 class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.integrity }}</h3>
        <p class="font-mono text-xs text-muted-foreground">sha256: {{ selected.content_sha256 }}</p>
        <p class="mt-1 text-xs text-muted-foreground">{{ T.pinHint }}</p>

        <div class="mt-5 flex flex-wrap items-center gap-3 border-t pt-4 text-xs">
          <a :href="reportUrl(selected)" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-destructive hover:underline">
            <ShieldAlert class="h-3.5 w-3.5" /> {{ T.reportHint }}
          </a>
          <a v-if="selected.source_repo" :href="selected.source_repo" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-primary hover:underline">
            <ExternalLink class="h-3.5 w-3.5" /> {{ T.sourceRepo }}
          </a>
        </div>
      </div>
    </Dialog>
  </div>
</template>
