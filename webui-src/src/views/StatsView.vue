<template>
  <div class="stats-view">
    <div class="view-header">
      <h2>统计分析</h2>
    </div>

    <div class="view-content">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else>
        <!-- 概览卡片 -->
        <div v-if="stats" class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">实体总数</div>
            <div class="stat-value">{{ stats.total_entities }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">关系总数</div>
            <div class="stat-value">{{ stats.total_relations }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">会话数</div>
            <div class="stat-value">{{ stats.total_sessions }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">用户数</div>
            <div class="stat-value">{{ stats.total_users }}</div>
          </div>
        </div>

        <!-- 图表区域 -->
        <div class="charts-container">
          <!-- 实体类型分布饼图 -->
          <div class="chart-card">
            <h3>实体类型分布</h3>
            <div ref="pieChartRef" class="chart"></div>
          </div>

          <!-- 时间线折线图 -->
          <div class="chart-card">
            <h3>实体创建趋势</h3>
            <div ref="lineChartRef" class="chart"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { statsApi } from '@/api/stats'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'

const loading = ref(false)
const stats = ref<any>(null)
const pieChartRef = ref<HTMLElement>()
const lineChartRef = ref<HTMLElement>()
let pieChart: ECharts | null = null
let lineChart: ECharts | null = null

const loadStats = async () => {
  loading.value = true
  try {
    const response = await statsApi.getOverview()
    stats.value = response.data
  } catch (err) {
    console.error('Failed to load stats:', err)
  } finally {
    loading.value = false
  }
}

const loadEntityTypes = async () => {
  try {
    const response = await statsApi.getEntityTypes()
    if (response.success && pieChartRef.value) {
      initPieChart(response.data.distribution)
    }
  } catch (err) {
    console.error('Failed to load entity types:', err)
  }
}

const loadTimeline = async () => {
  try {
    const response = await statsApi.getTimeline()
    if (response.success && lineChartRef.value) {
      initLineChart(response.data.timeline)
    }
  } catch (err) {
    console.error('Failed to load timeline:', err)
  }
}

const initPieChart = (distribution: any[]) => {
  if (!pieChartRef.value) return

  pieChart = echarts.init(pieChartRef.value)

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: {
        color: getComputedStyle(document.documentElement)
          .getPropertyValue('--color-text-primary')
          .trim(),
      },
    },
    series: [
      {
        name: '实体类型',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: getComputedStyle(document.documentElement)
            .getPropertyValue('--color-bg-primary')
            .trim(),
          borderWidth: 2,
        },
        label: {
          show: false,
          position: 'center',
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 20,
            fontWeight: 'bold',
          },
        },
        labelLine: {
          show: false,
        },
        data: distribution.map((item) => ({
          value: item.count,
          name: item.type,
        })),
      },
    ],
  }

  pieChart.setOption(option)
}

const initLineChart = (timeline: any[]) => {
  if (!lineChartRef.value) return

  lineChart = echarts.init(lineChartRef.value)

  const dates = timeline.map((item) => item.date)
  const counts = timeline.map((item) => item.count)

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}: {c} 个实体',
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        color: getComputedStyle(document.documentElement)
          .getPropertyValue('--color-text-secondary')
          .trim(),
      },
      axisLine: {
        lineStyle: {
          color: getComputedStyle(document.documentElement)
            .getPropertyValue('--color-border')
            .trim(),
        },
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: getComputedStyle(document.documentElement)
          .getPropertyValue('--color-text-secondary')
          .trim(),
      },
      axisLine: {
        lineStyle: {
          color: getComputedStyle(document.documentElement)
            .getPropertyValue('--color-border')
            .trim(),
        },
      },
      splitLine: {
        lineStyle: {
          color: getComputedStyle(document.documentElement)
            .getPropertyValue('--color-border-light')
            .trim(),
        },
      },
    },
    series: [
      {
        name: '实体数量',
        type: 'line',
        smooth: true,
        data: counts,
        lineStyle: {
          color: getComputedStyle(document.documentElement)
            .getPropertyValue('--color-accent')
            .trim(),
          width: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              {
                offset: 0,
                color: getComputedStyle(document.documentElement)
                  .getPropertyValue('--color-accent')
                  .trim() + '40',
              },
              {
                offset: 1,
                color: getComputedStyle(document.documentElement)
                  .getPropertyValue('--color-accent')
                  .trim() + '00',
              },
            ],
          },
        },
        itemStyle: {
          color: getComputedStyle(document.documentElement)
            .getPropertyValue('--color-accent')
            .trim(),
        },
      },
    ],
  }

  lineChart.setOption(option)
}

const handleResize = () => {
  pieChart?.resize()
  lineChart?.resize()
}

onMounted(async () => {
  await loadStats()
  await loadEntityTypes()
  await loadTimeline()

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChart?.dispose()
  lineChart?.dispose()
})

// 监听主题变化
watch(
  () => document.documentElement.getAttribute('data-theme'),
  () => {
    // 重新加载图表以应用新主题
    if (pieChart) {
      loadEntityTypes()
    }
    if (lineChart) {
      loadTimeline()
    }
  }
)
</script>

<style scoped>
.stats-view {
  padding: 24px;
  height: 100%;
  overflow: auto;
}

.view-header {
  margin-bottom: 24px;
}

.view-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.view-content {
  max-width: 1400px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.stat-card {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 24px;
  text-align: center;
}

.stat-label {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 36px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.charts-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
  gap: 24px;
}

.chart-card {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 24px;
}

.chart-card h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16px;
}

.chart {
  width: 100%;
  height: 400px;
}

.loading {
  text-align: center;
  padding: 48px;
  color: var(--color-text-secondary);
}
</style>
