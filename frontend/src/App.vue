<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Check,
  Copy,
  ExternalLink,
  Hash,
  List,
  Loader2,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Store,
  Terminal,
  TriangleAlert,
  Upload,
} from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import Select from '@/components/ui/Select.vue'
import Pagination from '@/components/ui/Pagination.vue'
import Dialog from '@/components/ui/Dialog.vue'
import FiltersSidebar from '@/components/FiltersSidebar.vue'
import { copyText } from '@/lib/clipboard'
import { T } from '@/ui-text'
import type { StepLibrary, StepTemplate } from '@/types'
import { groupPlugins, selectPluginVersion, detailPageUrl, type StepPlugin } from '@/lib/plugins'
import { NEW_TEMPLATE_URL, REPO_URL } from '@/types'

const library = ref<StepLibrary>({ templates: [], unparseable: [] })
const loading = ref(true)
const error = ref('')
const search = ref('')
const publisher = ref('all')
const engine = ref('all')
const category = ref('all')
const review = ref('all')
const selectedKeywords = ref<string[]>([])
const page = ref(1)
const PAGE_SIZE = 15
const showMobileFilters = ref(false)
const selected = ref<StepTemplate | null>(null)
const selectedPlugin = ref<StepPlugin | null>(null)
const detailOpen = ref(false)
const copiedCard = ref<string | null>(null)
const copiedDetail = ref(false)
const copiedUsage = ref(false)

async function copyUsesRef(t: StepTemplate, context: 'card' | 'detail' = 'card') {
  if (await copyText(`${t.id}@${t.version}`)) {
    if (context === 'card') {
      copiedCard.value = `${t.id}@${t.version}`
      setTimeout(() => {
        if (copiedCard.value === `${t.id}@${t.version}`) copiedCard.value = null
      }, 1500)
    } else {
      copiedDetail.value = true
      setTimeout(() => (copiedDetail.value = false), 1500)
    }
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

const allPlugins = computed(() => groupPlugins(library.value.templates))
const allTemplates = computed(() => allPlugins.value.map((plugin) => plugin.latest))

const publisherFacets = computed(() => countBy(allTemplates.value, (t) => t.publisher || 'community'))
const engineFacets = computed(() => countBy(allTemplates.value, (t) => t.engine))
const categoryFacets = computed(() => countBy(allTemplates.value, (t) => t.category || 'uncategorized'))
const keywordFacets = computed(() => {
  const counts = new Map<string, number>()
  for (const t of allTemplates.value)
    for (const keyword of t.keywords || []) counts.set(keyword, (counts.get(keyword) || 0) + 1)
  return [...counts.entries()]
    .filter(([value]) => !/[\u4e00-\u9fff\u3400-\u4dbf]/.test(value))
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
    category.value !== 'all' ||
    review.value !== 'all' ||
    selectedKeywords.value.length > 0 ||
    search.value.trim() !== '',
)

function clearFilters() {
  publisher.value = 'all'
  engine.value = 'all'
  category.value = 'all'
  review.value = 'all'
  selectedKeywords.value = []
  search.value = ''
}

const filtered = computed(() => {
  let list = allPlugins.value.slice()
  if (publisher.value !== 'all')
    list = list.filter((plugin) => (plugin.latest.publisher || 'community') === publisher.value)
  if (engine.value !== 'all') list = list.filter((plugin) => plugin.latest.engine === engine.value)
  if (category.value !== 'all')
    list = list.filter((plugin) => (plugin.latest.category || 'uncategorized') === category.value)
  if (review.value !== 'all')
    list = list.filter((plugin) => (review.value === 'reviewed' ? plugin.latest.reviewed : !plugin.latest.reviewed))
  if (selectedKeywords.value.length)
    list = list.filter((plugin) =>
      selectedKeywords.value.some((keyword) => (plugin.latest.keywords || []).includes(keyword)),
    )
  const q = search.value.trim().toLowerCase()
  if (q)
    list = list.filter((plugin) => {
      const t = plugin.latest
      const haystack = [
        t.id, t.name, t.category, t.description, t.description_zh, t.author, t.engine, ...(t.keywords || []),
      ].filter(Boolean).join(' ').toLowerCase()
      return haystack.includes(q)
    })
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paged = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filtered.value.slice(start, start + PAGE_SIZE)
})

watch([search, publisher, engine, category, review, selectedKeywords], () => (page.value = 1))

function openPlugin(plugin: StepPlugin) {
  selectedPlugin.value = plugin
  selected.value = plugin.latest
  detailOpen.value = true
}

function selectVersion(version: string) {
  selected.value = selectedPlugin.value ? selectPluginVersion(selectedPlugin.value, version) : null
  copiedDetail.value = false
  copiedUsage.value = false
}

function detailUrl(template: StepTemplate): string {
  return detailPageUrl(template.file)
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
            :category="category"
            :review="review"
            :selected-keywords="selectedKeywords"
            :publisher-facets="publisherFacets"
            :engine-facets="engineFacets"
            :category-facets="categoryFacets"
            :review-facets="reviewFacets"
            :keyword-facets="keywordFacets"
            :has-active-filters="hasActiveFilters"
            @update:publisher="publisher = $event"
            @update:engine="engine = $event"
            @update:category="category = $event"
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
            :category="category"
            :review="review"
            :selected-keywords="selectedKeywords"
            :publisher-facets="publisherFacets"
            :engine-facets="engineFacets"
            :category-facets="categoryFacets"
            :review-facets="reviewFacets"
            :keyword-facets="keywordFacets"
            :has-active-filters="hasActiveFilters"
            @update:publisher="publisher = $event"
            @update:engine="engine = $event"
            @update:category="category = $event"
            @update:review="review = $event"
            @update:selected-keywords="selectedKeywords = $event"
            @clear="clearFilters(); showMobileFilters = false"
          />
        </div>

        <!-- Community submission callout -->
        <div class="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed p-4">
          <div class="min-w-0">
            <div class="text-sm font-medium">Built something useful? Share it with the community.</div>
            <div class="text-xs text-muted-foreground mt-0.5">
              One YAML file per template — open a PR and CI validates it automatically.
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button size="sm" as="a" :href="NEW_TEMPLATE_URL" target="_blank">
              <Upload class="mr-1 h-3.5 w-3.5" /> Open a PR
            </Button>
            <Button variant="outline" size="sm" as="a" :href="`${REPO_URL}#authoring`" target="_blank">
              Authoring guide
            </Button>
          </div>
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
              v-for="plugin in paged"
              :key="plugin.id"
              class="group flex cursor-pointer flex-col p-5 transition-shadow hover:shadow-md"
              @click="openPlugin(plugin)"
            >
              <div>
                <div class="font-semibold leading-snug">{{ plugin.latest.name || plugin.id }}</div>
                <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <Badge v-if="plugin.latest.category" variant="secondary">{{ plugin.latest.category }}</Badge>
                  <Badge :variant="plugin.latest.reviewed ? 'reviewed' : 'unreviewed'" :title="plugin.latest.reviewed ? T.reviewedTip : T.unreviewedTip">
                    {{ plugin.latest.reviewed ? `✓ ${T.reviewed}` : T.unreviewed }}
                  </Badge>
                  <Badge :variant="(plugin.latest.publisher || 'community') === 'official' ? 'official' : 'community'">
                    {{ (plugin.latest.publisher || 'community') === 'official' ? T.official : T.community }}
                  </Badge>
                </div>
                <div class="mt-1.5 flex items-center gap-1">
                  <span class="font-mono text-xs text-muted-foreground">{{ plugin.id }} · v{{ plugin.latest.version }}</span>
                  <Badge v-if="plugin.versions.length > 1" variant="secondary">
                    {{ T.versionsCount(plugin.versions.length) }}
                  </Badge>
                  <button
                    class="copy-btn inline-flex h-5 w-5 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground"
                    :title="copiedCard === `${plugin.id}@${plugin.latest.version}` ? T.copied : T.copy"
                    :aria-label="`${T.copy}: ${plugin.id}@${plugin.latest.version}`"
                    @click.stop="copyUsesRef(plugin.latest)"
                  >
                    <Check v-if="copiedCard === `${plugin.id}@${plugin.latest.version}`" class="h-3 w-3 text-emerald-600" />
                    <Copy v-else class="h-3 w-3" />
                  </button>
                </div>
              </div>

              <p class="mt-3 line-clamp-3 flex-1 text-sm text-muted-foreground">{{ localized(plugin.latest) }}</p>

              <div class="mt-3 flex flex-wrap gap-1.5">
                <Badge variant="secondary" class="font-mono">{{ plugin.latest.engine }}</Badge>
                <Badge v-if="plugin.latest.default_timeout" variant="secondary" class="font-mono">{{ plugin.latest.default_timeout }}</Badge>
                <Badge variant="secondary">{{ T.inputsCount(plugin.latest.inputs.length) }}</Badge>
                <Badge v-if="plugin.latest.buz_compatible === false" variant="warn">
                  <ShieldAlert class="mr-0.5 h-3 w-3" /> {{ T.incompatible }}
                </Badge>
              </div>

              <div class="mt-4 flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
                <span class="truncate">{{ plugin.latest.author ? `${T.by} ${plugin.latest.author}` : '' }}</span>
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
        <!-- Header: reference (with copy) + badges + close -->
        <div class="flex items-start justify-between gap-4 border-b pb-4">
          <div class="min-w-0">
            <div class="flex items-center gap-1.5">
              <span class="truncate font-mono text-sm font-semibold">{{ selected.id }}@{{ selected.version }}</span>
              <Select
                v-if="selectedPlugin && selectedPlugin.versions.length > 1"
                :model-value="selected.version"
                :aria-label="T.selectVersion"
                class="w-36"
                @update:model-value="selectVersion"
              >
                <option v-for="version in selectedPlugin.versions" :key="version.version" :value="version.version">
                  {{ version.version }}
                </option>
              </Select>
              <a
                class="text-xs text-primary hover:underline"
                :href="detailUrl(selected)"
                target="_blank"
                rel="noopener"
              >
                {{ T.versionPage }}
              </a>
              <button
                class="copy-btn inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                :title="copiedDetail ? T.copied : T.copy"
                aria-label="Copy uses reference"
                @click="copyUsesRef(selected, 'detail')"
              >
                <Check v-if="copiedDetail" class="h-3.5 w-3.5 text-emerald-600" />
                <Copy v-else class="h-3.5 w-3.5" />
              </button>
            </div>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <Badge v-if="selected.category" variant="secondary">{{ selected.category }}</Badge>
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

        <!-- Description -->
        <p class="mt-4 text-sm leading-relaxed">{{ localized(selected) }}</p>

        <!-- Meta chips -->
        <div class="mt-4 flex flex-wrap gap-1.5">
          <Badge v-if="selected.category" variant="secondary">{{ selected.category }}</Badge>
          <Badge variant="secondary" class="font-mono">{{ selected.engine }}</Badge>
          <Badge v-if="selected.default_timeout" variant="secondary">{{ T.timeout }}: {{ selected.default_timeout }}</Badge>
          <Badge v-if="selected.license" variant="secondary">{{ selected.license }}</Badge>
          <Badge v-if="selected.author" variant="secondary">{{ T.by }} {{ selected.author }}</Badge>
          <Badge v-if="selected.buz_compatible === false" variant="warn">
            <ShieldAlert class="mr-0.5 h-3 w-3" /> {{ T.incompatible }}
          </Badge>
        </div>

        <!-- Usage -->
        <section class="mt-6">
          <h3 class="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Terminal class="h-3.5 w-3.5" /> {{ T.usage }}
          </h3>
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
        </section>

        <!-- Inputs -->
        <section v-if="selected.inputs.length" class="mt-6">
          <h3 class="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <List class="h-3.5 w-3.5" /> {{ T.inputs }}
          </h3>
          <div class="overflow-hidden rounded-md border">
            <table class="w-full text-xs">
              <thead>
                <tr class="border-b bg-muted/60 text-left text-muted-foreground">
                  <th class="py-1.5 pr-3 pl-3 font-medium">{{ T.name }}</th>
                  <th class="py-1.5 pr-3 font-medium">{{ T.type }}</th>
                  <th class="py-1.5 pr-3 font-medium">{{ T.required }}</th>
                  <th class="py-1.5 pr-3 font-medium">{{ T.masking }}</th>
                  <th class="py-1.5 pr-3 font-medium">{{ T.description }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="input in selected.inputs" :key="input.name" class="border-b last:border-0">
                  <td class="py-1.5 pr-3 pl-3 font-mono">{{ input.name }}</td>
                  <td class="py-1.5 pr-3">{{ input.type || 'string' }}</td>
                  <td class="py-1.5 pr-3">{{ input.required ? T.yes : T.no }}</td>
                  <td class="py-1.5 pr-3">{{ input.masking ? T.yes : T.no }}</td>
                  <td class="py-1.5 pr-3 text-muted-foreground">{{ input.description || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Integrity -->
        <section class="mt-6">
          <h3 class="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Hash class="h-3.5 w-3.5" /> {{ T.integrity }}
          </h3>
          <div class="rounded-md border bg-muted/40 p-3">
            <p class="break-all font-mono text-xs">sha256: {{ selected.content_sha256 }}</p>
            <p class="mt-1.5 text-xs text-muted-foreground">{{ T.pinHint }}</p>
          </div>
        </section>

        <!-- Footer links -->
        <div class="mt-6 flex flex-wrap items-center gap-3 border-t pt-4 text-xs">
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
