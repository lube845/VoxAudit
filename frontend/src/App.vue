<template>
  <router-view />
</template>

<script setup>
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif;
}

#app {
  min-height: 100vh;
  background-color: var(--va-paper);
}

/* Lucide 图标在 el-icon 内随字号缩放 */
.el-icon svg {
  width: 1em;
  height: 1em;
}
</style>