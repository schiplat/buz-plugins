<script setup lang="ts">
const open = defineModel<boolean>({ default: false })
function close() {
  open.value = false
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      leave-active-class="transition duration-100 ease-in"
      leave-to-class="opacity-0"
    >
      <div v-if="open" class="fixed inset-0 z-50 bg-black/40" @click="close()" />
    </Transition>
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      leave-active-class="transition duration-100 ease-in"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="open"
        class="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg max-h-[85vh] overflow-y-auto"
        role="dialog"
        aria-modal="true"
      >
        <slot />
      </div>
    </Transition>
  </Teleport>
</template>
