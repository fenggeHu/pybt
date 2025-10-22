<template>
  <div ref="chartRef" class="chart" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

interface SeriesItem {
  name: string
  data: Array<[string, number]>
}

const props = defineProps<{ series: SeriesItem[]; height?: number }>()

const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const render = () => {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    legend: { top: 0 },
    xAxis: {
      type: 'category',
      data: props.series[0]?.data.map((item) => item[0]) ?? [],
      axisLabel: { color: '#808080' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#808080' }
    },
    series: props.series.map((s) => ({
      name: s.name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: s.data
    }))
  }
  chart.setOption(option)
}

onMounted(() => {
  render()
  window.addEventListener('resize', render)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', render)
  chart?.dispose()
  chart = null
})

watch(() => props.series, render, { deep: true })
</script>

<style scoped>
.chart {
  width: 100%;
  height: 320px;
}
</style>
