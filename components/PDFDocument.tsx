import React from 'react';
import { Page, Text, View, Document, StyleSheet } from '@react-pdf/renderer';
import { format } from 'date-fns';
import { Operation, Balance, OperationType } from '../types';

const styles = StyleSheet.create({
    page: {
        flexDirection: 'column',
        backgroundColor: '#F9FAFB',
        padding: 35,
        fontFamily: 'Helvetica',
    },
    header: {
        marginBottom: 25,
        paddingBottom: 15,
        paddingTop: 20,
        paddingLeft: 25,
        paddingRight: 25,
        backgroundColor: '#1F2937',
        borderRadius: 8,
    },
    title: {
        fontSize: 28,
        fontWeight: 'bold',
        color: '#FFFFFF',
        marginBottom: 8,
        letterSpacing: 0.5,
    },
    subtitle: {
        fontSize: 12,
        color: '#D1D5DB',
        fontWeight: 'normal',
    },
    balanceSection: {
        marginBottom: 20,
    },
    balanceTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#1F2937',
        marginTop: 15,
        marginBottom: 12,
        paddingBottom: 8,
        paddingLeft: 10,
        borderLeftWidth: 4,
        borderLeftColor: '#3B82F6',
        backgroundColor: '#EFF6FF',
        paddingTop: 8,
        paddingRight: 10,
    },
    table: {
        display: 'flex',
        width: 'auto',
        borderRadius: 6,
        overflow: 'hidden',
        borderStyle: 'solid',
        borderWidth: 1,
        borderColor: '#D1D5DB',
        backgroundColor: '#FFFFFF',
    },
    tableRow: {
        margin: 'auto',
        flexDirection: 'row',
    },
    tableColHeader: {
        width: '25%',
        borderStyle: 'solid',
        borderWidth: 1,
        borderLeftWidth: 0,
        borderTopWidth: 0,
        borderColor: '#E5E7EB',
        backgroundColor: '#F3F4F6',
        padding: 8,
    },
    tableCol: {
        width: '25%',
        borderStyle: 'solid',
        borderWidth: 1,
        borderLeftWidth: 0,
        borderTopWidth: 0,
        borderColor: '#E5E7EB',
        padding: 8,
        backgroundColor: '#FFFFFF',
    },
    tableCellHeader: {
        margin: 'auto',
        fontSize: 10,
        fontWeight: 'bold',
        color: '#1F2937',
        textTransform: 'uppercase',
        letterSpacing: 0.5,
    },
    tableCell: {
        margin: 'auto',
        fontSize: 10,
        color: '#4B5563',
    },
    tableCellIncome: {
        margin: 'auto',
        fontSize: 10,
        color: '#059669',
        fontWeight: 'bold',
    },
    tableCellExpense: {
        margin: 'auto',
        fontSize: 10,
        color: '#DC2626',
        fontWeight: 'bold',
    },
    tableCellBalance: {
        margin: 'auto',
        fontSize: 10,
        color: '#1F2937',
        fontWeight: 'bold',
    },
    totalRow: {
        flexDirection: 'row',
        marginTop: 12,
        justifyContent: 'flex-end',
        backgroundColor: '#EFF6FF',
        padding: 10,
        borderRadius: 6,
    },
    totalText: {
        fontSize: 13,
        fontWeight: 'bold',
        color: '#1F2937',
    },
    emptyMessage: {
        fontSize: 11,
        color: '#9CA3AF',
        fontStyle: 'italic',
        padding: 20,
        textAlign: 'center',
        backgroundColor: '#F9FAFB',
        borderRadius: 6,
    },
    summaryCard: {
        backgroundColor: '#FFFFFF',
        padding: 15,
        borderRadius: 8,
        marginBottom: 15,
        borderLeftWidth: 4,
        borderLeftColor: '#3B82F6',
    }
});

interface PDFDocumentProps {
    operations: Operation[];
    balances: Balance[];
    dateRange: { start: Date; end: Date };
    associationName: string;
}

const PDFDocument: React.FC<PDFDocumentProps> = ({ operations, balances, dateRange, associationName }) => {

    const summaryData = balances.map(balance => {
        const balanceOps = operations.filter(op => op.balanceId === balance.id);

        const previousOps = balanceOps.filter(op => new Date(op.date) < dateRange.start);
        const initialIncome = previousOps.filter(op => op.type === OperationType.INCOME).reduce((sum, op) => sum + op.amount, 0);
        const initialExpense = previousOps.filter(op => op.type === OperationType.EXPENSE).reduce((sum, op) => sum + op.amount, 0);
        const startBalance = balance.initialAmount + initialIncome - initialExpense;

        const periodOps = balanceOps.filter(op => {
            const opDate = new Date(op.date);
            return opDate >= dateRange.start && opDate <= dateRange.end;
        });

        const periodIncome = periodOps.filter(op => op.type === OperationType.INCOME).reduce((sum, op) => sum + op.amount, 0);
        const periodExpense = periodOps.filter(op => op.type === OperationType.EXPENSE).reduce((sum, op) => sum + op.amount, 0);
        const endBalance = startBalance + periodIncome - periodExpense;

        return {
            balance,
            startBalance,
            endBalance,
            periodIncome,
            periodExpense,
            periodOps: periodOps.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
        };
    });

    return (
        <Document>
            {/* Summary Page */}
            <Page size="A4" style={styles.page}>
                <View style={styles.header}>
                    <Text style={styles.title}>{associationName}</Text>
                    <Text style={styles.subtitle}>
                        Report Period: {format(dateRange.start, 'MMM dd, yyyy')} - {format(dateRange.end, 'MMM dd, yyyy')}
                    </Text>
                </View>

                <Text style={styles.balanceTitle}>Summary</Text>
                <View style={styles.table}>
                    <View style={styles.tableRow}>
                        <View style={{ ...styles.tableColHeader, width: '20%' }}>
                            <Text style={styles.tableCellHeader}>Balance</Text>
                        </View>
                        <View style={{ ...styles.tableColHeader, width: '20%' }}>
                            <Text style={styles.tableCellHeader}>Start</Text>
                        </View>
                        <View style={{ ...styles.tableColHeader, width: '20%' }}>
                            <Text style={styles.tableCellHeader}>Income</Text>
                        </View>
                        <View style={{ ...styles.tableColHeader, width: '20%' }}>
                            <Text style={styles.tableCellHeader}>Expense</Text>
                        </View>
                        <View style={{ ...styles.tableColHeader, width: '20%' }}>
                            <Text style={styles.tableCellHeader}>End</Text>
                        </View>
                    </View>
                    {summaryData.map((data) => (
                        <View style={styles.tableRow} key={data.balance.id}>
                            <View style={{ ...styles.tableCol, width: '20%' }}>
                                <Text style={styles.tableCell}>{data.balance.name}</Text>
                            </View>
                            <View style={{ ...styles.tableCol, width: '20%' }}>
                                <Text style={styles.tableCellBalance}>{data.startBalance.toFixed(2)} €</Text>
                            </View>
                            <View style={{ ...styles.tableCol, width: '20%' }}>
                                <Text style={styles.tableCellIncome}>+{data.periodIncome.toFixed(2)} €</Text>
                            </View>
                            <View style={{ ...styles.tableCol, width: '20%' }}>
                                <Text style={styles.tableCellExpense}>-{data.periodExpense.toFixed(2)} €</Text>
                            </View>
                            <View style={{ ...styles.tableCol, width: '20%' }}>
                                <Text style={styles.tableCellBalance}>{data.endBalance.toFixed(2)} €</Text>
                            </View>
                        </View>
                    ))}
                </View>
            </Page>

            {/* Detailed Pages */}
            {summaryData.map((data) => (
                <Page key={data.balance.id} size="A4" style={styles.page}>
                    <View style={styles.balanceSection}>
                        <Text style={styles.balanceTitle}>{data.balance.name} - Details</Text>

                        {data.periodOps.length > 0 ? (
                            <View style={styles.table}>
                                <View style={styles.tableRow}>
                                    <View style={styles.tableColHeader}>
                                        <Text style={styles.tableCellHeader}>Date</Text>
                                    </View>
                                    <View style={styles.tableColHeader}>
                                        <Text style={styles.tableCellHeader}>Name</Text>
                                    </View>
                                    <View style={styles.tableColHeader}>
                                        <Text style={styles.tableCellHeader}>Type</Text>
                                    </View>
                                    <View style={styles.tableColHeader}>
                                        <Text style={styles.tableCellHeader}>Amount</Text>
                                    </View>
                                </View>
                                {data.periodOps.map((op) => (
                                    <View style={styles.tableRow} key={op.id}>
                                        <View style={styles.tableCol}>
                                            <Text style={styles.tableCell}>{format(new Date(op.date), 'MMM dd, yyyy')}</Text>
                                        </View>
                                        <View style={styles.tableCol}>
                                            <Text style={styles.tableCell}>{op.name}</Text>
                                        </View>
                                        <View style={styles.tableCol}>
                                            <Text style={styles.tableCell}>{op.type}</Text>
                                        </View>
                                        <View style={styles.tableCol}>
                                            <Text style={op.type === OperationType.EXPENSE ? styles.tableCellExpense : styles.tableCellIncome}>
                                                {op.type === OperationType.EXPENSE ? '-' : '+'}{op.amount.toFixed(2)} €
                                            </Text>
                                        </View>
                                    </View>
                                ))}
                            </View>
                        ) : (
                            <Text style={styles.emptyMessage}>No operations for this period.</Text>
                        )}

                        <View style={styles.totalRow}>
                            <Text style={styles.totalText}>End Balance: {data.endBalance.toFixed(2)} €</Text>
                        </View>
                    </View>
                </Page>
            ))}
        </Document>
    );
};

export default PDFDocument;
