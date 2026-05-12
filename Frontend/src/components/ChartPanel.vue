<template>
  <el-card class="chart-panel">
    <template #header>数据图表</template>

    <div v-if="!charts || !charts.length" class="chart-empty">
      <div class="chart-empty-icon">📊</div>
      <div class="chart-empty-text">暂无图表数据</div>
    </div>

    <div v-else class="chart-grid" ref="gridRef">
      <div
        v-for="chart in charts"
        :key="chart.chartId"
        class="chart-item"
      >
        <div class="chart-item-title">{{ chart.title }}</div>
        <div
          class="chart-canvas"
          :ref="el => mountChart(el, chart)"
        ></div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'

defineProps({
  charts: { type: Array, required: true },
})

const gridRef = ref(null)
const instances = []
let resizeObserver = null

// Brand-aligned ECharts theme
const BRAND_COLORS = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#36cfc9']

function buildOption(spec) {
  const baseTextStyle = { color: '#606266', fontSize: 12 }

  if (spec.chartType === 'pie') {
    return {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)',
      },
      legend: {
        bottom: 0,
        textStyle: baseTextStyle,
      },
      color: BRAND_COLORS,
      series: spec.series.map(s => ({
        name: s.name,
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['50%', '45%'],
        label: {
          formatter: '{b}\n{c}条',
          fontSize: 11,
          color: '#606266',
        },
        data: spec.xAxis.map((name, i) => ({ name, value: s.data[i] })),
      })),
    }
  }

  const isLine = spec.chartType === 'line'

  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 16, bottom: 36, containLabel: true },
    xAxis: {
      type: 'category',
      data: spec.xAxis,
      axisLine: { lineStyle: { color: '#e8eaed' } },
      axisLabel: { color: '#909399', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f2f5' } },
      axisLabel: { color: '#909399', fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    color: BRAND_COLORS,
    series: spec.series.map((s, idx) => {
      const color = BRAND_COLORS[idx % BRAND_COLORS.length]
      if (isLine) {
        return {
          name: s.name,
          type: 'line',
          data: s.data,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { width: 2, color },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: color + '33' },
                { offset: 1, color: color + '05' },
              ],
            },
          },
        }
      }
      return {
        name: s.name,
        type: 'bar',
        data: s.data,
        barMaxWidth: 48,
        itemStyle: {
          borderRadius: [3, 3, 0, 0],
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color },
              { offset: 1, color: color + '99' },
            ],
          },
        },
      }
    }),
  }
}

function mountChart(el, spec) {
  if (!el) return
  nextTick(() => {
    const existing = echarts.getInstanceByDom(el)
    if (existing) return
    const instance = echarts.init(el, null, { renderer: 'canvas' })
    instance.setOption(buildOption(spec))
    instances.push(instance)
  })
}

onMounted(() => {
  if (!gridRef.value) return
  resizeObserver = new ResizeObserver(() => {
    instances.forEach(inst => {
      if (!inst.isDisposed()) inst.resize()
    })
  })
  resizeObserver.observe(gridRef.value)
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
  instances.forEach(i => { if (!i.isDisposed()) i.dispose() })
})
</script>

<style scoped>
.chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  color: #c0c4cc;
}

.chart-empty-icon {
  font-size: 32px;
  opacity: 0.5;
}

.chart-empty-text {
  font-size: 13px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (max-width: 700px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
}

.chart-item {
  background: #fafafa;
  border: 1px solid #f0f2f5;
  border-radius: 6px;
  padding: 12px 14px;
  min-width: 0;
}

.chart-item-title {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
  text-align: center;
}

.chart-canvas {
  width: 100%;
  height: 260px;
}
</style>
