import React, { useMemo, useState, useRef, useEffect } from 'react';
import { Operation } from '../types';
import { format } from 'date-fns';
import ConfirmationModal from './ConfirmationModal';

interface OperationsTableProps {
  title: 'Income' | 'Expenses';
  operations: Operation[];
  onEdit: (operation: Operation) => void;
  onDelete: (operationId: string) => void;
}

const OperationsTable: React.FC<OperationsTableProps> = ({ title, operations, onEdit, onDelete }) => {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [operationToDelete, setOperationToDelete] = useState<Operation | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const toggleGroup = (group: string) => {
    setCollapsedGroups(prev => ({
      ...prev,
      [group]: !prev[group]
    }));
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null);
        setMenuPosition(null);
      }
    };
    const handleScroll = () => {
      if (openMenuId) {
        setOpenMenuId(null);
        setMenuPosition(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('scroll', handleScroll, true);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [openMenuId]);

  const toggleMenu = (id: string, e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (openMenuId === id) {
      setOpenMenuId(null);
      setMenuPosition(null);
    } else {
      const rect = e.currentTarget.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const menuHeight = 100;

      let top = rect.bottom;
      if (spaceBelow < menuHeight) {
        top = rect.top - menuHeight;
      }

      setMenuPosition({
        top: top,
        left: rect.right - 128,
      });
      setOpenMenuId(id);
    }
  };

  const handleDeleteClick = (op: Operation) => {
    setOperationToDelete(op);
    setOpenMenuId(null);
    setMenuPosition(null);
  };

  const confirmDelete = () => {
    if (operationToDelete) {
      onDelete(operationToDelete.id);
      setOperationToDelete(null);
    }
  };

  const groupedOperations = useMemo(() => {
    return operations.reduce((acc, op) => {
      (acc[op.group] = acc[op.group] || []).push(op);
      return acc;
    }, {} as Record<string, Operation[]>);
  }, [operations]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(amount);
  };

  const titleColor = title === 'Income' ? 'text-green-600' : 'text-red-600';

  return (
    <div>
      <h4 className={`text-lg font-semibold mb-3 ${titleColor}`}>{title}</h4>
      <div className="space-y-4">
        {Object.keys(groupedOperations).length > 0 ? (
          Object.keys(groupedOperations).map((group) => {
            const ops = groupedOperations[group];
            return (
              <div key={group} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div
                  className="bg-gray-50 px-6 py-3 border-b border-gray-200 flex justify-between items-center cursor-pointer select-none hover:bg-gray-100 transition-colors"
                  onClick={() => toggleGroup(group)}
                >
                  <h5 className="font-semibold text-gray-700 text-sm uppercase tracking-wider">{group}</h5>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className={`h-5 w-5 text-gray-400 transform transition-transform duration-200 ${collapsedGroups[group] ? '-rotate-90' : 'rotate-0'}`}
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </div>
                {!collapsedGroups[group] && (
                  <div className="divide-y divide-gray-100">
                    {ops.map(op => (
                      <div key={op.id} className="group relative flex items-center justify-between p-5 hover:bg-gray-50 transition-colors duration-150">
                        <div className="flex-1 min-w-0 pr-4">
                          <div className="flex items-center justify-between mb-1">
                            <p className="text-base font-semibold text-gray-900 truncate">{op.name}</p>
                            <p className="text-sm text-gray-500 whitespace-nowrap ml-4">
                              {(() => {
                                try {
                                  return format(new Date(op.date), 'MMM dd, yyyy');
                                } catch (e) {
                                  return 'Invalid Date';
                                }
                              })()}
                            </p>
                          </div>
                          <p className="text-sm text-gray-500 truncate">{op.description}</p>
                        </div>

                        <div className="flex items-center pl-4 border-l border-gray-100 ml-4">
                          <div className={`text-base font-bold ${titleColor} mr-6 whitespace-nowrap`}>
                            {formatCurrency(op.amount)}
                          </div>
                          <div className="relative">
                            <button
                              onClick={(e) => toggleMenu(op.id, e)}
                              className="p-2 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 focus:outline-none transition-colors"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="text-center py-10 bg-gray-50 rounded-lg border border-dashed border-gray-300">
            <p className="text-gray-500">No {title.toLowerCase()} for this period.</p>
          </div>
        )}
      </div>

      {/* Fixed Menu Portal */}
      {openMenuId && menuPosition && (
        <div
          ref={menuRef}
          className="fixed z-50 w-32 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
          style={{ top: menuPosition.top, left: menuPosition.left }}
        >
          <div className="py-1">
            <button
              onClick={() => {
                const op = operations.find(o => o.id === openMenuId);
                if (op) onEdit(op);
                setOpenMenuId(null);
                setMenuPosition(null);
              }}
              className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
            >
              Edit
            </button>
            {(() => {
              const op = operations.find(o => o.id === openMenuId);
              if (op?.invoice) {
                return (
                  <button
                    onClick={() => {
                      window.open(op.invoice, '_blank');
                      setOpenMenuId(null);
                      setMenuPosition(null);
                    }}
                    className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
                  >
                    Voir la facture
                  </button>
                );
              }
              return null;
            })()}
            <button
              onClick={() => {
                const op = operations.find(o => o.id === openMenuId);
                if (op) handleDeleteClick(op);
              }}
              className="block w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-gray-100"
            >
              Delete
            </button>
          </div>
        </div>
      )}

      <ConfirmationModal
        isOpen={!!operationToDelete}
        onClose={() => setOperationToDelete(null)}
        onConfirm={confirmDelete}
        title="Delete Operation"
        message={`Are you sure you want to delete the operation "${operationToDelete?.name}"? This action cannot be undone.`}
        confirmText="Delete"
        isDanger={true}
      />
    </div>
  );
};

export default OperationsTable;
