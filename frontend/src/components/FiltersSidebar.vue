<script setup lang="ts">
import { T } from '@/ui-text'

export interface FilterFacet {
  value: string
  label: string
  count: number
}

const props = defineProps<{
  publisher: string
  engine: string
  category: string
  review: string
  selectedKeywords: string[]
  publisherFacets: FilterFacet[]
  engineFacets: FilterFacet[]
  categoryFacets: FilterFacet[]
  reviewFacets: FilterFacet[]
  keywordFacets: FilterFacet[]
  hasActiveFilters: boolean
}>()

const emit = defineEmits<{
  (e: 'update:publisher', value: string): void
  (e: 'update:engine', value: string): void
  (e: 'update:category', value: string): void
  (e: 'update:review', value: string): void
  (e: 'update:selectedKeywords', value: string[]): void
  (e: 'clear'): void
}>()

function toggleKeyword(keyword: string) {
  const next = props.selectedKeywords.includes(keyword)
    ? props.selectedKeywords.filter((k) => k !== keyword)
    : [...props.selectedKeywords, keyword]
  emit('update:selectedKeywords', next)
}
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold">{{ T.filters }}</h2>
      <button
        v-if="hasActiveFilters"
        class="text-xs text-primary hover:underline"
        @click="emit('clear')"
      >
        {{ T.clearFilters }}
      </button>
    </div>

    <div>
      <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.publisher }}</h3>
      <button
        v-for="facet in publisherFacets"
        :key="facet.value"
        class="flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-sm hover:bg-muted"
        :class="publisher === facet.value ? 'font-medium' : 'text-muted-foreground'"
        @click="emit('update:publisher', facet.value)"
      >
        <span :class="publisher === facet.value ? 'text-foreground' : ''">{{ facet.label }}</span>
        <span class="text-xs text-muted-foreground">{{ facet.count }}</span>
      </button>
    </div>

    <div>
      <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.engine }}</h3>
      <button
        v-for="facet in engineFacets"
        :key="facet.value"
        class="flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-sm hover:bg-muted"
        :class="engine === facet.value ? 'font-medium' : 'text-muted-foreground'"
        @click="emit('update:engine', facet.value)"
      >
        <span :class="engine === facet.value ? 'text-foreground' : ''">{{ facet.label }}</span>
        <span class="text-xs text-muted-foreground">{{ facet.count }}</span>
      </button>
    </div>

    <div>
      <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.category }}</h3>
      <button
        v-for="facet in categoryFacets"
        :key="facet.value"
        class="flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-sm hover:bg-muted"
        :class="category === facet.value ? 'font-medium' : 'text-muted-foreground'"
        @click="emit('update:category', facet.value)"
      >
        <span :class="category === facet.value ? 'text-foreground' : ''">{{ facet.label }}</span>
        <span class="text-xs text-muted-foreground">{{ facet.count }}</span>
      </button>
    </div>

    <div>
      <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.reviewStatus }}</h3>
      <button
        v-for="facet in reviewFacets"
        :key="facet.value"
        class="flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-sm hover:bg-muted"
        :class="review === facet.value ? 'font-medium' : 'text-muted-foreground'"
        @click="emit('update:review', facet.value)"
      >
        <span :class="review === facet.value ? 'text-foreground' : ''">{{ facet.label }}</span>
        <span class="text-xs text-muted-foreground">{{ facet.count }}</span>
      </button>
    </div>

    <div v-if="keywordFacets.length">
      <h3 class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ T.keywords }}</h3>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="facet in keywordFacets"
          :key="facet.value"
          class="rounded-full border px-2.5 py-0.5 text-xs transition-colors"
          :class="selectedKeywords.includes(facet.value)
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-border text-muted-foreground hover:border-primary/50'"
          @click="toggleKeyword(facet.value)"
        >
          {{ facet.label }} <span class="text-muted-foreground">{{ facet.count }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
