<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

const props = defineProps<{ page: number; totalPages: number; class?: string }>()
const emit = defineEmits<{ (e: 'update:page', page: number): void }>()

const pages = computed<(number | '…')[]>(() => {
  const total = props.totalPages
  const current = props.page
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const out: (number | '…')[] = [1]
  const window = [current - 1, current, current + 1].filter((p) => p > 1 && p < total)
  if (window[0] !== undefined && window[0] > 2) out.push('…')
  out.push(...window)
  if (window[window.length - 1] !== undefined && window[window.length - 1] < total - 1) out.push('…')
  out.push(total)
  return out
})

function go(page: number) {
  if (page >= 1 && page <= props.totalPages && page !== props.page) emit('update:page', page)
}
</script>

<template>
  <nav v-if="totalPages > 1" :class="cn('flex items-center justify-center gap-1', props?.class)" aria-label="pagination">
    <button
      :disabled="page <= 1"
      class="inline-flex h-8 items-center gap-1 rounded-md border px-2.5 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
      @click="go(page - 1)"
    >
      <ChevronLeft class="h-3.5 w-3.5" />
      <slot name="prev" />
    </button>
    <template v-for="(p, i) in pages" :key="`${p}-${i}`">
      <span v-if="p === '…'" class="h-8 px-2 leading-8 text-muted-foreground">…</span>
      <button
        v-else
        :class="cn('inline-flex h-8 w-8 items-center justify-center rounded-md border text-sm font-medium transition-colors',
          p === page ? 'border-primary bg-primary text-primary-foreground' : 'border-transparent hover:bg-muted')"
        @click="go(p)"
      >
        {{ p }}
      </button>
    </template>
    <button
      :disabled="page >= totalPages"
      class="inline-flex h-8 items-center gap-1 rounded-md border px-2.5 text-sm font-medium transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
      @click="go(page + 1)"
    >
      <slot name="next" />
      <ChevronRight class="h-3.5 w-3.5" />
    </button>
  </nav>
</template>
