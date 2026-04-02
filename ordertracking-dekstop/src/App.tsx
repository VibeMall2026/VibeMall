/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { motion } from "motion/react";
import { ChevronRight, Search, ShoppingBag } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

type TimelineEvent = {
  status: string;
  date: string;
  description: string;
  isCompleted: boolean;
};

type OrderItemData = {
  name: string;
  id: string;
  qty: number;
  price: number;
  image: string;
};

type ApiRecentOrder = {
  order_number: string;
  status: string;
};

function cleanText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function parseTimelineDate(text: string): { status: string; date: string } {
  const [status, date] = text.split(/\s+[\-–]\s+/);
  return {
    status: cleanText(status || text),
    date: cleanText(date || ""),
  };
}

function parseOrderTrackingHtml(html: string) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const orderNumber = cleanText(doc.querySelector(".order-number")?.textContent || "").replace(/^Order\s*#?/i, "");
  const statusBadge = cleanText(doc.querySelector(".status-badge")?.textContent || "Ordered");

  const timelineEvents: TimelineEvent[] = Array.from(doc.querySelectorAll(".timeline .timeline-item")).map((item) => {
    const titleRaw = cleanText(item.querySelector(".timeline-title")?.textContent || "Order Update");
    const description = cleanText(item.querySelector(".timeline-description")?.textContent || "Tracking update available.");
    const parsed = parseTimelineDate(titleRaw);
    const completed = item.classList.contains("completed") || !item.classList.contains("pending");

    return {
      status: parsed.status,
      date: parsed.date,
      description,
      isCompleted: completed,
    };
  });

  const infoCards = Array.from(doc.querySelectorAll(".order-info .info-card")).map((card) => ({
    label: cleanText(card.querySelector(".label")?.textContent || ""),
    value: cleanText(card.querySelector(".value")?.textContent || ""),
  }));

  const orderItems: OrderItemData[] = Array.from(doc.querySelectorAll(".products-section .product-card")).map((card, index) => {
    const name = cleanText(card.querySelector(".product-name")?.textContent || `Item ${index + 1}`);
    const meta = cleanText(card.querySelector(".product-meta")?.textContent || "");
    const image = (card.querySelector("img") as HTMLImageElement | null)?.src || "";
    const qtyMatch = meta.match(/qty\s*[:x]?\s*(\d+)/i);
    const priceMatch = meta.match(/[₹$]\s*([\d,.]+)/);

    return {
      name,
      id: `${100000 + index}`,
      qty: qtyMatch ? Number(qtyMatch[1]) : 1,
      price: priceMatch ? Number(priceMatch[1].replace(/,/g, "")) : 0,
      image,
    };
  });

  return { orderNumber, statusBadge, timelineEvents, infoCards, orderItems };
}

export default function App() {
  const [orderNumberInput, setOrderNumberInput] = useState("");
  const [activeOrderNumber, setActiveOrderNumber] = useState("");
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [orderItems, setOrderItems] = useState<OrderItemData[]>([]);
  const [infoCards, setInfoCards] = useState<{ label: string; value: string }[]>([]);
  const [recentOrders, setRecentOrders] = useState<ApiRecentOrder[]>([]);
  const [statusLabel, setStatusLabel] = useState("Ordered");
  const [loading, setLoading] = useState(false);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const totals = useMemo(() => {
    const subtotal = orderItems.reduce((acc, item) => acc + (item.price || 0), 0);
    const shipping = subtotal > 0 ? 2.25 : 0;
    const tax = 0;
    return {
      subtotal,
      shipping,
      tax,
      total: subtotal + shipping + tax,
    };
  }, [orderItems]);

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
        // Keep manual order tracking available even if stats fail.
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
      setErrorMessage("Please enter an order number.");
      return;
    }

    setErrorMessage("");
    setLoading(true);

    try {
      const response = await fetch(`/order/track/${encodeURIComponent(orderNumber)}/`, {
        credentials: 'include',
        redirect: 'follow',
      });

      if (response.url.includes('/login')) {
        throw new Error('Please sign in to view tracking details.');
      }

      if (!response.ok) {
        throw new Error('Unable to load tracking details for this order.');
      }

      const html = await response.text();
      const parsed = parseOrderTrackingHtml(html);

      setActiveOrderNumber(parsed.orderNumber || orderNumber);
      setStatusLabel(parsed.statusBadge || 'Ordered');
      setTimelineEvents(parsed.timelineEvents);
      setOrderItems(parsed.orderItems);
      setInfoCards(parsed.infoCards);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to track this order right now.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-6 md:p-12 lg:p-20 max-w-7xl mx-auto pt-28">
      <header className="fixed top-0 left-0 right-0 z-50 flex justify-between items-center px-6 md:px-12 py-6 md:py-8 bg-brand-bg/85 backdrop-blur-lg border-b border-black/5">
        <span className="text-2xl md:text-3xl font-serif tracking-tighter text-brand-text">VIBEMALL</span>
        <div className="flex items-center gap-5 text-brand-text">
          <Search size={20} strokeWidth={1.5} />
          <ShoppingBag size={20} strokeWidth={1.5} />
        </div>
      </header>

      <form onSubmit={trackOrder} className="mb-10 bg-white rounded-2xl p-5 shadow-sm max-w-2xl">
        <label className="block text-xs tracking-[0.2em] uppercase text-gray-500 mb-2">Track Order</label>
        <div className="flex flex-col md:flex-row gap-3">
          <input
            type="text"
            value={orderNumberInput}
            onChange={(e) => setOrderNumberInput(e.target.value)}
            placeholder="Enter order number"
            className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-brand-accent"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-brand-text text-white rounded-xl px-6 py-3 text-xs tracking-[0.2em] uppercase font-semibold disabled:opacity-60"
          >
            {loading ? 'Loading...' : 'Track Now'}
          </button>
        </div>
        {errorMessage && <p className="text-xs text-red-600 mt-3">{errorMessage}</p>}
        {loadingRecent ? (
          <p className="text-xs text-gray-500 mt-3">Loading recent orders...</p>
        ) : recentOrders.length > 0 ? (
          <div className="flex flex-wrap gap-2 mt-3">
            {recentOrders.slice(0, 4).map((order) => (
              <button
                key={order.order_number}
                type="button"
                onClick={() => setOrderNumberInput(order.order_number)}
                className="text-[10px] px-3 py-1 rounded-full border border-gray-200 text-gray-600 hover:text-black"
              >
                {order.order_number}
              </button>
            ))}
          </div>
        ) : null}
      </form>

      <header className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-gray-300 pb-12 mb-12">
        <div className="space-y-2">
          <h1 className="font-serif text-5xl md:text-7xl tracking-tight uppercase leading-none">
            {activeOrderNumber ? `Order #${activeOrderNumber}` : 'Order Tracking'}
          </h1>
          <h2 className="font-serif text-5xl md:text-7xl tracking-tight uppercase leading-none">
            {statusLabel}
          </h2>
        </div>

        <div className="mt-8 md:mt-0 grid grid-cols-2 gap-x-12 gap-y-4 text-xs tracking-widest uppercase font-medium">
          <div>
            <p className="text-gray-500 mb-1">Latest Update</p>
            <p className="font-serif text-3xl normal-case tracking-normal">{infoCards[0]?.value || 'Pending update'}</p>
          </div>
          <div>
            <p className="text-gray-500 mb-1">Estimated Delivery</p>
            <p className="font-serif text-3xl normal-case tracking-normal">{infoCards[1]?.value || 'TBD'}</p>
          </div>
          <div className="col-span-1">
            <p className="text-gray-500">Payment</p>
          </div>
          <div className="col-span-1">
            <p className="text-gray-500">{infoCards[2]?.value || 'Carrier updates will appear here'}</p>
          </div>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-16">
        <section className="lg:col-span-2">
          <div className="relative space-y-12 pl-12">
            <div className="absolute left-[1.15rem] top-2 bottom-2 w-0.5 bg-brand-text" />

            {timelineEvents.map((event, index) => (
              <motion.div
                key={`${event.status}-${index}`}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="relative"
              >
                <div className="absolute -left-12 top-1.5 w-10 h-10 flex items-center justify-center">
                  <div className="w-6 h-6 rounded-full border-2 border-brand-text bg-brand-bg flex items-center justify-center">
                    <div className={`w-3 h-3 rounded-full ${event.isCompleted ? 'bg-brand-accent' : 'bg-gray-300'}`} />
                  </div>
                </div>

                <div className="space-y-1">
                  <h3 className="font-bold text-lg tracking-tight uppercase">
                    {event.status}
                    {event.date && <span className="font-normal normal-case text-gray-600"> - {event.date}</span>}
                  </h3>
                  <p className="text-gray-600 leading-relaxed max-w-xl">{event.description}</p>
                </div>
              </motion.div>
            ))}
            {timelineEvents.length === 0 && <p className="text-sm text-gray-500">Track an order to see timeline updates.</p>}
          </div>
        </section>

        <section className="space-y-8 border-l border-gray-300 pl-8 lg:pl-16">
          <h3 className="font-serif text-2xl">Order Details</h3>

          <div className="space-y-6">
            {orderItems.map((item, index) => (
              <div key={`${item.id}-${index}`} className="flex gap-4 group">
                <div className="w-20 h-20 bg-gray-100 flex-shrink-0 overflow-hidden">
                  <img
                    src={item.image}
                    alt={item.name}
                    className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all duration-500"
                    referrerPolicy="no-referrer"
                  />
                </div>
                <div className="flex-grow flex justify-between items-start">
                  <div className="text-sm">
                    <p className="font-bold uppercase tracking-tight">{item.name}</p>
                    <p className="text-gray-500">Item #: {item.id}</p>
                    <p className="text-gray-500">QTY: {item.qty}</p>
                  </div>
                  <p className="text-sm font-medium">${item.price.toFixed(2)}</p>
                </div>
              </div>
            ))}
            {orderItems.length === 0 && <p className="text-sm text-gray-500">Track an order to see item details.</p>}
          </div>

          <div className="pt-8 border-t border-gray-300 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Subtotal</span>
              <span>${totals.subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Shipping</span>
              <span>${totals.shipping.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Tax</span>
              <span>${totals.tax.toFixed(2)}</span>
            </div>
            <div className="flex justify-between pt-4 font-bold text-lg">
              <span>Total</span>
              <span>${totals.total.toFixed(2)}</span>
            </div>
          </div>

          <div className="pt-8 space-y-4">
            <p className="text-sm text-gray-600">Need help with your shipment?</p>
            <a href="#" className="inline-flex items-center gap-1 font-bold border-b-2 border-brand-text pb-0.5 hover:text-brand-accent hover:border-brand-accent transition-colors">
              Need Help?
              <ChevronRight size={14} />
            </a>
          </div>
        </section>
      </main>

      <footer className="w-full py-12 mt-14 px-8 bg-white border-t border-gray-200 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="text-[10px] tracking-[0.2em] uppercase text-gray-600">© 2026 VIBEMALL ATELIER. ALL RIGHTS RESERVED.</div>
        <div className="flex gap-8 text-[10px] tracking-[0.2em] uppercase text-gray-700">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
          <a href="#">Shipping & Returns</a>
        </div>
      </footer>
    </div>
  );
}
