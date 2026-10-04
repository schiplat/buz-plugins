<script setup lang="ts">
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        outline: 'text-foreground',
        reviewed: 'border-emerald-600/30 bg-emerald-600/10 text-emerald-700 dark:text-emerald-500',
        unreviewed: 'border-border bg-muted text-muted-foreground',
        official: 'border-blue-600/30 bg-blue-600/10 text-blue-700 dark:text-blue-400',
        community: 'border-border bg-muted text-muted-foreground',
        warn: 'border-amber-600/30 bg-amber-600/10 text-amber-700 dark:text-amber-500',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

const props = withDefaults(
  defineProps<{
    variant?: 'default' | 'secondary' | 'outline' | 'reviewed' | 'unreviewed' | 'official' | 'community' | 'warn'
    class?: string
  }>(),
  { variant: 'default' },
)
</script>

<template>
  <span :class="cn(badgeVariants({ variant }), props.class)"><slot /></span>
</template>
