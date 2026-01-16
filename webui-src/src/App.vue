<template>
  <router-view />
</template>

<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

// 初始化主题
useTheme()
</script>
