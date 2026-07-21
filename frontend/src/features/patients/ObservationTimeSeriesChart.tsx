import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ClinicalObservation } from "@/types/patient";
import type { ObservationTypeConfig } from "./observationConfig";

interface ChartPoint {
  measuredAt: string;
  measuredAtLabel: string;
  [seriesKey: string]: string | number;
}

function buildChartData(
  config: ObservationTypeConfig,
  observations: ClinicalObservation[],
): ChartPoint[] {
  // Grafico de serie temporal: ordem cronologica (a listagem chega do
  // backend em ordem decrescente por `measured_at`).
  const chronological = [...observations].reverse();
  return chronological.map((observation) => {
    const point: ChartPoint = {
      measuredAt: observation.measured_at,
      measuredAtLabel: new Date(observation.measured_at).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }),
    };
    for (const series of config.series) {
      const raw = observation.value[series.valueKey];
      if (typeof raw === "number") point[series.valueKey] = raw;
    }
    return point;
  });
}

interface ObservationTimeSeriesChartProps {
  config: ObservationTypeConfig;
  observations: ClinicalObservation[];
}

/**
 * Grafico de linha de serie temporal para um tipo de observacao clinica,
 * com a faixa ideal/normal exibida como uma banda de referencia atras
 * das linhas. Pressao arterial plota duas series (sistolica/diastolica)
 * no mesmo grafico.
 */
export function ObservationTimeSeriesChart({
  config,
  observations,
}: ObservationTimeSeriesChartProps) {
  const data = buildChartData(config, observations);

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="measuredAtLabel" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} unit={config.unit ? ` ${config.unit}` : undefined} />
          <Tooltip
            formatter={(value, name) => [`${value ?? "-"} ${config.unit}`.trim(), name]}
          />
          <Legend />
          {config.series
            .filter((series) => !series.hideIdealBand)
            .map((series) => (
              <ReferenceArea
                key={`${series.valueKey}-ideal`}
                y1={series.idealMin}
                y2={series.idealMax}
                fill={series.color}
                fillOpacity={0.08}
                stroke={series.color}
                strokeOpacity={0.3}
                strokeDasharray="4 4"
                ifOverflow="extendDomain"
                label={{
                  value: `${series.label} ideal: ${series.idealMin}-${series.idealMax}`,
                  position: "insideTopLeft",
                  fontSize: 10,
                  fill: series.color,
                }}
              />
            ))}
          {config.series.map((series) => (
            <Line
              key={series.valueKey}
              type="monotone"
              dataKey={series.valueKey}
              name={series.label}
              stroke={series.color}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
