import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Download,
  ExternalLink,
  Star,
  TrendingUp,
  ChevronUp,
  ChevronDown,
  Package,
  ShoppingCart,
} from 'lucide-react';
import type { Product } from '../../types';

interface ResultsPanelProps {
  results: Product[];
  isLoading: boolean;
}

type SortField = 'price' | 'rating' | 'name';
type SortDirection = 'asc' | 'desc';

export function ResultsPanel({ results, isLoading }: ResultsPanelProps) {
  const [sortField, setSortField] = useState<SortField>('price');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const sortedResults = useMemo(() => {
    return [...results].sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'price':
          comparison = a.price - b.price;
          break;
        case 'rating':
          comparison = (b.rating || 0) - (a.rating || 0);
          break;
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [results, sortField, sortDirection]);

  const bestValue = useMemo(() => {
    if (results.length === 0) return null;
    // Best value = lowest price with rating > 4
    const goodRated = results.filter((p) => (p.rating || 0) >= 4);
    if (goodRated.length === 0) return results.reduce((a, b) => (a.price < b.price ? a : b));
    return goodRated.reduce((a, b) => (a.price < b.price ? a : b));
  }, [results]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection(field === 'rating' ? 'desc' : 'asc');
    }
  };

  const exportToCsv = () => {
    const headers = ['Name', 'Price', 'Rating', 'Source', 'URL'];
    const rows = results.map((p) => [
      `"${p.name.replace(/"/g, '""')}"`,
      p.price.toFixed(2),
      p.rating?.toFixed(1) || 'N/A',
      p.source,
      p.url,
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'results.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? (
      <ChevronUp className="w-3 h-3" />
    ) : (
      <ChevronDown className="w-3 h-3" />
    );
  };

  return (
    <motion.div
      className="h-full flex flex-col"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4 px-1">
        <div className="flex items-center gap-2">
          <ShoppingCart className="w-5 h-5 text-accent-cyan" />
          <h2 className="text-lg font-semibold text-white">Results</h2>
          {results.length > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-white/10 text-white/60">
              {results.length} items
            </span>
          )}
        </div>
        {results.length > 0 && (
          <motion.button
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all"
            style={{
              background: 'rgba(0, 245, 255, 0.1)',
              border: '1px solid rgba(0, 245, 255, 0.3)',
            }}
            whileHover={{ scale: 1.02, background: 'rgba(0, 245, 255, 0.2)' }}
            whileTap={{ scale: 0.98 }}
            onClick={exportToCsv}
          >
            <Download className="w-4 h-4" />
            Export CSV
          </motion.button>
        )}
      </div>

      {/* Content */}
      <div
        className="flex-1 rounded-xl overflow-hidden"
        style={{
          background: 'rgba(18, 18, 26, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div
              key="loading"
              className="h-full flex flex-col items-center justify-center gap-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="relative">
                <motion.div
                  className="w-16 h-16 rounded-full border-2 border-accent-cyan/30"
                  style={{ borderTopColor: 'var(--accent-cyan)' }}
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                />
              </div>
              <p className="text-white/40">Collecting results...</p>
            </motion.div>
          ) : results.length === 0 ? (
            <motion.div
              key="empty"
              className="h-full flex flex-col items-center justify-center gap-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.div
                className="w-16 h-16 rounded-xl flex items-center justify-center"
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px dashed rgba(255, 255, 255, 0.1)',
                }}
              >
                <Package className="w-8 h-8 text-white/20" />
              </motion.div>
              <p className="text-white/40">Results will appear here</p>
            </motion.div>
          ) : (
            <motion.div
              key="results"
              className="h-full overflow-auto"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Table header */}
              <div
                className="sticky top-0 grid grid-cols-12 gap-2 p-3 text-xs font-medium text-white/50 uppercase tracking-wider"
                style={{ background: 'rgba(18, 18, 26, 0.95)' }}
              >
                <button
                  className="col-span-5 flex items-center gap-1 hover:text-white/80 transition-colors text-left"
                  onClick={() => handleSort('name')}
                >
                  Product <SortIcon field="name" />
                </button>
                <button
                  className="col-span-2 flex items-center gap-1 hover:text-white/80 transition-colors"
                  onClick={() => handleSort('price')}
                >
                  Price <SortIcon field="price" />
                </button>
                <button
                  className="col-span-2 flex items-center gap-1 hover:text-white/80 transition-colors"
                  onClick={() => handleSort('rating')}
                >
                  Rating <SortIcon field="rating" />
                </button>
                <div className="col-span-2">Source</div>
                <div className="col-span-1"></div>
              </div>

              {/* Table rows */}
              <div className="divide-y divide-white/5">
                {sortedResults.map((product, index) => {
                  const isBestValue = bestValue && product.url === bestValue.url;
                  return (
                    <motion.div
                      key={`${product.url}-${index}`}
                      className={`grid grid-cols-12 gap-2 p-3 items-center transition-colors ${
                        isBestValue ? 'bg-accent-cyan/5' : 'hover:bg-white/5'
                      }`}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      {/* Product name */}
                      <div className="col-span-5 flex items-center gap-2">
                        {isBestValue && (
                          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent-cyan/20 text-accent-cyan">
                            <TrendingUp className="w-3 h-3" />
                            Best
                          </span>
                        )}
                        <span className="text-sm text-white/90 truncate">{product.name}</span>
                      </div>

                      {/* Price */}
                      <div className="col-span-2">
                        <span className="text-sm font-medium text-accent-cyan">
                          ${product.price.toFixed(2)}
                        </span>
                      </div>

                      {/* Rating */}
                      <div className="col-span-2 flex items-center gap-1">
                        {product.rating ? (
                          <>
                            <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
                            <span className="text-sm text-white/70">{product.rating.toFixed(1)}</span>
                          </>
                        ) : (
                          <span className="text-sm text-white/30">N/A</span>
                        )}
                      </div>

                      {/* Source */}
                      <div className="col-span-2">
                        <span className="px-2 py-1 rounded-md text-xs bg-white/5 text-white/60 capitalize">
                          {product.source}
                        </span>
                      </div>

                      {/* Link */}
                      <div className="col-span-1 flex justify-end">
                        <a
                          href={product.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-white/40 hover:text-white"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export default ResultsPanel;
