import {
  BarElement, CategoryScale, Chart as ChartJS, type ChartOptions, Legend, LinearScale, LineElement, PointElement,
  Tooltip,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";

import { num } from "../lib/format";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend);
ChartJS.defaults.color = "#8f9096";
ChartJS.defaults.font.family = '"Barlow", system-ui, sans-serif';
ChartJS.defaults.borderColor = "rgba(46, 48, 53, .8)";
ChartJS.defaults.plugins.legend.labels.boxWidth = 12;

/** gedeckte Serienfarben, auf dunklem Grund gut unterscheidbar */
export const PALETTE = ["#5b93f0", "#e3b341", "#4cb782", "#e5535f", "#a383e0", "#57b8c9", "#e0875a", "#d67fb0",
  "#9bb85a", "#b8b6b0", "#7f8fd9", "#c29a6b", "#6fc7a4", "#c9a0dc"];

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
            backgroundColor: points.map((p) => (p.positive ? "rgba(47, 212, 138, .75)" : "rgba(255, 77, 94, .75)")),
            borderRadius: 4,
          }],
        }}
      />
    </div>
  );
}
