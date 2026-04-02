import { 
  Package, 
  Calendar, 
  Headphones, 
  Check, 
  ChevronRight,
  Search,
  ShoppingBag,
} from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';

type ApiRecentOrder = {
  order_number: string;
  date: string;
  status: string;
};

type TrackStep = { label: string; status: 'completed' | 'pending' };
type TrackedItem = { id: number; name: string; meta: string; image: string };
type InfoCardData = { icon: 'package' | 'calendar' | 'support'; title: string; description: string; isAction?: boolean };

const STEP_LABELS = ['Ordered', 'Processing', 'Shipped', 'Out for Delivery', 'Delivered'];

function toSteps(statusText: string): TrackStep[] {
  const status = statusText.toUpperCase();
  let completedIndex = 0;

  if (status.includes('PROCESS')) completedIndex = 1;
  if (status.includes('SHIP')) completedIndex = 2;
  if (status.includes('OUT') || status.includes('DELIVERY')) completedIndex = 3;
  if (status.includes('DELIVERED') || status.includes('COMPLETED')) completedIndex = 4;

  return STEP_LABELS.map((label, index) => ({
    label,
    status: index <= completedIndex ? 'completed' : 'pending',
  }));
}

function cleanText(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

function parseOrderTrackingHtml(html: string) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const orderNumber = cleanText(doc.querySelector('.order-number')?.textContent || '').replace(/^Order\s*#?/i, '');
  const badge = cleanText(doc.querySelector('.status-badge')?.textContent || 'Ordered');

  const infoCards = Array.from(doc.querySelectorAll('.order-info .info-card')).map((card) => {
    const label = cleanText(card.querySelector('.label')?.textContent || 'Update');
    const value = cleanText(card.querySelector('.value')?.textContent || '');
    return { label, value };
  });

  const timelineEntries = Array.from(doc.querySelectorAll('.timeline .timeline-item .timeline-title')).map((node) => cleanText(node.textContent || '')).filter(Boolean);

  const items = Array.from(doc.querySelectorAll('.products-section .product-card')).map((card, index) => {
    const name = cleanText(card.querySelector('.product-name')?.textContent || `Item ${index + 1}`);
    const meta = cleanText(card.querySelector('.product-meta')?.textContent || '');
    const image = (card.querySelector('img') as HTMLImageElement | null)?.src || '';
    return {
      id: index + 1,
      name,
      meta,
      image,
    };
  });

  return { orderNumber, badge, infoCards, timelineEntries, items };
}

export default function App() {
  const [orderNumberInput, setOrderNumberInput] = useState('');
  const [activeOrderNumber, setActiveOrderNumber] = useState('');
  const [statusLabel, setStatusLabel] = useState('Ordered');
  const [timelineEntries, setTimelineEntries] = useState<string[]>([]);
  const [items, setItems] = useState<TrackedItem[]>([]);
  const [infoCards, setInfoCards] = useState<InfoCardData[]>([]);
  const [recentOrders, setRecentOrders] = useState<ApiRecentOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const steps = useMemo(() => toSteps(statusLabel), [statusLabel]);
  const completedSteps = steps.filter((step) => step.status === 'completed').length;
  const progressPercent = ((Math.max(completedSteps - 1, 0)) / (STEP_LABELS.length - 1)) * 100;

  useEffect(() => {
    let cancelled = false;
    const fetchRecentOrders = async () => {
      setLoadingRecent(true);
      try {
        const response = await fetch('/api/profile/stats/', { credentials: 'include' });
        if (!response.ok) return;
        const data = await response.json();
        const orders = Array.isArray(data?.recent_orders) ? data.recent_orders : [];
        if (!cancelled) {
          setRecentOrders(orders);
          if (orders.length > 0) {
            setOrderNumberInput(orders[0].order_number);
          }
        }
      } catch {
        // Ignore and keep manual tracking input.
      } finally {
        if (!cancelled) {
          setLoadingRecent(false);
        }
      }
    };

    fetchRecentOrders();
    return () => {
      cancelled = true;
    };
  }, []);

  const trackOrder = async (e: FormEvent) => {
    e.preventDefault();
    const orderNumber = orderNumberInput.trim();
    if (!orderNumber) {
      setErrorMessage('Please enter an order number.');
      return;
    }

    setErrorMessage('');
    setLoading(true);

    try {
      const response = await fetch(`/order/track/${encodeURIComponent(orderNumber)}/`, {
        credentials: 'include',
        redirect: 'follow',
      });

      if (response.url.includes('/login')) {
        throw new Error('Please sign in to view your order tracking details.');
      }

      if (!response.ok) {
        throw new Error('Unable to load tracking details for this order number.');
      }

      const html = await response.text();
      const parsed = parseOrderTrackingHtml(html);

      setActiveOrderNumber(parsed.orderNumber || orderNumber);
      setStatusLabel(parsed.badge || 'Ordered');
      setTimelineEntries(parsed.timelineEntries);
      setItems(parsed.items);

      const mappedCards: InfoCardData[] = [
        {
          icon: 'package',
          title: parsed.infoCards[0]?.label || 'Latest Update',
          description: parsed.infoCards[0]?.value || parsed.timelineEntries[0] || 'Tracking details are being updated.',
        },
        {
          icon: 'calendar',
          title: parsed.infoCards[1]?.label || 'Estimated Delivery',
          description: parsed.infoCards[1]?.value || 'Delivery information will appear here shortly.',
        },
        {
          icon: 'support',
          title: 'Help & Support',
          description: 'Contact Concierge',
          isAction: true,
        },
      ];

      setInfoCards(mappedCards);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to track this order right now.');
    } finally {
      setLoading(false);
    }
  };

  const iconForCard = (iconType: InfoCardData['icon']) => {
    if (iconType === 'calendar') return <Calendar className="text-gray-900" size={24} />;
    if (iconType === 'support') return <Headphones className="text-gray-900" size={24} />;
    return <Package className="text-gray-900" size={24} />;
  };

  return (
    <div className="min-h-screen font-sans max-w-md mx-auto pt-24 pb-10 px-6">
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-xl flex justify-between items-center px-8 py-6 border-b border-gray-100">
        <span className="text-2xl font-semibold tracking-tighter text-gray-900">VIBEMALL</span>
        <div className="flex items-center gap-6 text-primary">
          <Search className="w-5 h-5 stroke-[1.5px]" />
          <ShoppingBag className="w-5 h-5 stroke-[1.5px]" />
        </div>
      </header>

      <form onSubmit={trackOrder} className="mb-8 bg-white rounded-2xl p-4 shadow-sm space-y-3">
        <label className="block text-[10px] font-medium tracking-[0.2em] uppercase text-gray-500">Track Order</label>
        <input
          type="text"
          value={orderNumberInput}
          onChange={(e) => setOrderNumberInput(e.target.value)}
          placeholder="Enter order number"
          className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-luxury-gold"
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-black text-white rounded-xl py-3 text-xs tracking-[0.2em] uppercase font-semibold disabled:opacity-60"
        >
          {loading ? 'Loading...' : 'Track Now'}
        </button>
        {errorMessage && <p className="text-xs text-red-600">{errorMessage}</p>}
        {loadingRecent ? (
          <p className="text-xs text-gray-500">Loading recent orders...</p>
        ) : recentOrders.length > 0 ? (
          <div className="flex flex-wrap gap-2 pt-1">
            {recentOrders.slice(0, 3).map((order) => (
              <button
                key={order.order_number}
                type="button"
                onClick={() => setOrderNumberInput(order.order_number)}
                className="text-[10px] px-2 py-1 rounded-full border border-gray-200 text-gray-600 hover:text-black"
              >
                {order.order_number}
              </button>
            ))}
          </div>
        ) : null}
      </form>

      {/* Header / Stepper */}
      <div className="mb-10 pt-4">
        <div className="flex justify-between items-center relative mb-2">
          {/* Progress Line Background */}
          <div className="absolute top-1/2 left-0 w-full h-[2px] bg-gray-200 -translate-y-1/2 z-0" />
          
          {/* Active Progress Line */}
          <div 
            className="absolute top-1/2 left-0 h-[2px] bg-luxury-gold -translate-y-1/2 z-0 transition-all duration-500" 
            style={{ width: `${progressPercent}%` }}
          />

          {steps.map((step, idx) => (
            <div key={idx} className="relative z-10 flex flex-col items-center">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                step.status === 'completed' 
                  ? 'bg-luxury-gold text-white' 
                  : 'bg-gray-200 text-gray-400'
              }`}>
                {step.status === 'completed' ? <Check size={12} strokeWidth={3} /> : null}
              </div>
            </div>
          ))}
        </div>
        
        <div className="flex justify-between w-full">
          {steps.map((step, idx) => (
            <span key={idx} className={`text-[10px] font-medium text-center w-1/5 leading-tight ${
              step.status === 'completed' ? 'text-gray-900' : 'text-gray-400'
            }`}>
              {step.label}
            </span>
          ))}
        </div>
      </div>

      {/* Order Title */}
      <motion.h1 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-3xl font-semibold mb-8 tracking-tight"
      >
        {activeOrderNumber ? `Order #${activeOrderNumber}` : 'Track Your Order'}
      </motion.h1>

      {/* Info Cards */}
      <div className="space-y-4 mb-10">
        {infoCards.map((card, index) => (
          <InfoCard
            key={card.title}
            icon={iconForCard(card.icon)}
            title={card.title}
            description={card.description}
            isAction={card.isAction}
            delay={0.1 + index * 0.1}
          />
        ))}
      </div>

      {timelineEntries.length > 0 && (
        <div className="mb-10 bg-white rounded-2xl p-5 shadow-sm">
          <h2 className="text-lg font-semibold mb-3">Timeline</h2>
          <div className="space-y-2">
            {timelineEntries.slice(0, 5).map((entry) => (
              <p key={entry} className="text-sm text-gray-600 leading-relaxed">• {entry}</p>
            ))}
          </div>
        </div>
      )}

      {/* Items Section */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-4">Items in your shipment</h2>
        <div className="flex overflow-x-auto pb-4 gap-4 no-scrollbar">
          {items.map((item, idx) => (
            <motion.div 
              key={item.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.4 + idx * 0.1 }}
              className="flex-shrink-0 w-48 bg-white rounded-2xl p-4 shadow-sm"
            >
              <div className="aspect-square bg-luxury-cream rounded-xl mb-3 overflow-hidden flex items-center justify-center">
                <img 
                  src={item.image} 
                  alt={item.name} 
                  className="w-full h-full object-cover mix-blend-multiply"
                  referrerPolicy="no-referrer"
                />
              </div>
              <h3 className="text-sm font-medium leading-snug mb-1 line-clamp-2 h-10">
                {item.name}
              </h3>
              <p className="text-sm text-gray-500">{item.meta || 'Qty: 1'}</p>
            </motion.div>
          ))}
          {items.length === 0 && (
            <p className="text-sm text-gray-500">Track an order to see shipment items.</p>
          )}
        </div>
      </div>

      <footer className="w-full py-10 bg-[#f0eee9] flex flex-col items-center gap-4 rounded-2xl mt-8">
        <div className="font-body text-[10px] tracking-[0.2em] uppercase text-primary opacity-70 text-center">
          © 2026 VIBEMALL ATELIER. ALL RIGHTS RESERVED.
        </div>
      </footer>
    </div>
  );
}

function InfoCard({ icon, title, description, isAction = false, delay = 0 }) {
  return (
    <motion.div 
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay }}
      className="bg-white rounded-2xl p-5 flex items-start gap-4 shadow-sm"
    >
      <div className="w-12 h-12 bg-luxury-cream rounded-xl flex items-center justify-center flex-shrink-0">
        {icon}
      </div>
      <div className="flex-grow">
        <h3 className="text-lg font-semibold mb-0.5">{title}</h3>
        <p className={`text-sm ${isAction ? 'text-gray-600 font-medium' : 'text-gray-500 leading-relaxed'}`}>
          {description}
        </p>
      </div>
      {isAction && <ChevronRight className="text-gray-300 mt-1" size={20} />}
    </motion.div>
  );
}

