import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Balance, Operation } from '../types';
import { format, eachDayOfInterval, isBefore } from 'date-fns';

interface OperationsChartProps {
  balances: Balance[];
  allOperations: Operation[];
  dateRange: { start: Date; end: Date };
}

const OperationsChart: React.FC<OperationsChartProps> = ({
  balances,
  allOperations,
  dateRange,
}) => {
  const chartData = useMemo(() => {
    if (!balances || !allOperations || !dateRange) return { data: [], colors: [] };

    const validOperations = allOperations.filter(
      (op) => op && op.date && !isNaN(new Date(op.date).getTime())
    );
    const days = eachDayOfInterval(dateRange);

    const balanceColors = ['#1f2937', '#6b7280', '#ef4444', '#10b981', '#3b82f6', '#a855f7'];

    const data = days.map((day) => {
      const entry: { date: string; [key: string]: number | string } = {
        date: format(day, 'MMM dd'),
      };

      balances.forEach((balance) => {
        const balanceAtStartOfRange =
          balance.initialAmount +
          validOperations
            .filter(
              (op) => op.balanceId === balance.id && isBefore(new Date(op.date), dateRange.start)
            )
            .reduce((acc, op) => acc + (op.type === 'income' ? op.amount : -op.amount), 0);

        const operationsInPeriodUntilDay = validOperations
          .filter((op) => {
            const opDate = new Date(op.date);
            return op.balanceId === balance.id && opDate >= dateRange.start && opDate <= day;
          })
          .reduce((acc, op) => acc + (op.type === 'income' ? op.amount : -op.amount), 0);

        entry[balance.name] = balanceAtStartOfRange + operationsInPeriodUntilDay;
      });

      return entry;
    });

    return { data, colors: balanceColors };
  }, [balances, allOperations, dateRange]);

  if (!balances || !balances.length) {
    return <p>No balances to display.</p>;
  }

  if (!chartData.data.length) {
    return <p>No data to display for this period.</p>;
  }

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={chartData.data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#6b7280" />
          <YAxis
            tick={{ fontSize: 12 }}
            stroke="#6b7280"
            tickFormatter={(value) =>
              new Intl.NumberFormat('fr-FR', {
                notation: 'compact',
                compactDisplay: 'short',
              }).format(value as number)
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#ffffff',
              border: '1px solid #e5e7eb',
              borderRadius: '0.5rem',
            }}
            formatter={(value) =>
              new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(
                value as number
              )
            }
          />
          <Legend wrapperStyle={{ fontSize: '14px' }} />
          {balances.map((balance, index) => (
            <Line
              key={balance.id}
              type="monotone"
              dataKey={balance.name}
              stroke={chartData.colors[index % chartData.colors.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default OperationsChart;
