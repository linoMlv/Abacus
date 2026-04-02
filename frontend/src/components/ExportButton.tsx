import React from 'react';
import { PDFDownloadLink } from '@react-pdf/renderer';
import PDFDocument from './PDFDocument';
import { Operation, Balance } from '../types';
import { format } from 'date-fns';

interface ExportButtonProps {
  operations: Operation[];
  balances: Balance[];
  dateRange: { start: Date; end: Date };
  associationName: string;
}

const ExportButton: React.FC<ExportButtonProps> = ({
  operations,
  balances,
  dateRange,
  associationName,
}) => {
  return (
    <PDFDownloadLink
      document={
        <PDFDocument
          operations={operations}
          balances={balances}
          dateRange={dateRange}
          associationName={associationName}
        />
      }
      fileName={`abacus_export_${format(dateRange.start, 'yyyy-MM-dd')}_${format(dateRange.end, 'yyyy-MM-dd')}.pdf`}
      className="text-sm font-medium text-gray-600 hover:text-gray-900 transition flex items-center space-x-1"
    >
      {({ blob: _blob, url: _url, loading, error: _error }) => (
        <>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="w-5 h-5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
            />
          </svg>
          <span>{loading ? 'Loading...' : 'Export PDF'}</span>
        </>
      )}
    </PDFDownloadLink>
  );
};

export default ExportButton;
