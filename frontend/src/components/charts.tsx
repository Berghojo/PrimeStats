import {
  BarElement, CategoryScale, Chart as ChartJS, type ChartOptions, Legend, LinearScale, LineElement, PointElement,
  Tooltip,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";

import { num } from "../lib/format";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend);
ChartJS.defaults.color = "#8d99b3";
ChartJS.defaults.borderColor = "rgba(38, 49, 80, .6)";
ChartJS.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
ChartJS.defaults.plugins.legend.labels.boxWidth = 12;

export const PALETTE = ["#7c5cff", "#20d3c2", "#ffb547", "#ff5a6a", "#4c8dff", "#2fd48a", "#f472b6",
  "#a3e635", "#fb923c", "#38bdf8", "#c084fc", "#facc15", "#94a3b8", "#e879f9"];

export interface LineSeries {
  label: string;
  data: (number | null)[];
  color: string;
  dashed?: boolean;
  /** Stichprobengröße pro Minute (für den Tooltip) */
  counts?: number[];
}

export function MinuteLineChart({ series, yTitle, height = 420 }: { series: LineSeries[]; yTitle?: string; height?: number }) {
  const length = Math.max(0, ...series.map((s) => s.data.length));
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    spanGaps: true,
    elements: { point: { radius: 0, hoverRadius: 4 }, line: { tension: 0.25, borderWidth: 2 } },
    scales: {
      x: { title: { display: true, text: "Minute" }, grid: { display: false } },
      y: { title: { display: !!yTitle, text: yTitle }, ticks: { callback: (v) => num(Number(v), 0) } },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (c) => `${c.dataset.label}: ${c.parsed.y === null ? "–" : num(c.parsed.y)}`,
          afterLabel: (c) => {
            const counts = series[c.datasetIndex]?.counts;
            return counts ? `n = ${counts[c.dataIndex] ?? 0}` : "";
          },
        },
      },
    },
  };
  return (
    <div className="chart-box" style={{ height }}>
      <Line
        options={options}
        data={{
          labels: Array.from({ length }, (_, i) => i),
          datasets: series.map((s) => ({
            label: s.label, data: s.data, borderColor: s.color, backgroundColor: s.color, borderDash: s.dashed ? [5, 4] : [],
          })),
        }}
      />
    </div>
  );
}

export interface BarPoint { label: string; value: number | null; positive: boolean; tooltip: string[] }

export function ResultBarChart({ points, height = 260 }: { points: BarPoint[]; height?: number }) {
  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { title: (items) => points[items[0].dataIndex].label, label: (c) => points[c.dataIndex].tooltip } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
      y: { ticks: { callback: (v) => num(Number(v), 0) } },
    },
  };
  return (
    <div className="chart-box" style={{ height }}>
      <Bar
        options={options}
        data={{
          labels: points.map((p) => p.label),
          datasets: [{
            data: points.map((p) => p.value),
            backgroundColor: points.map((p) => (p.positive ? "rgba(47, 212, 138, .75)" : "rgba(255, 90, 106, .75)")),
            borderRadius: 4,
          }],
        }}
      />
    </div>
  );
}
