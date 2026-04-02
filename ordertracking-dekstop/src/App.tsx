/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { motion } from "motion/react";
import { ChevronRight } from "lucide-react";

const timelineEvents = [
  {
    status: "DELIVERED",
    date: "Oct 26, 09:30 AM",
    description: "Delivered restraad your Leather Tote Bag. We delivere to your delivery, under space door and come recommaed our orders as you.",
    isCompleted: true,
  },
  {
    status: "OUT FOR DELIVERY",
    date: "Oct 26, 06:45 AM",
    description: "Out for delivery - stan s winemarkee approach your nist out for delivery. Weak your delivery awaotives order deliver.",
    isCompleted: true,
  },
  {
    status: "ARRIVED AT FACILITY",
    date: "Oct 25, 11:15 PM",
    description: "Arrived at Facility - tennery start Oct 25, 11:15 PM, personality enceived an arding and ecrived at outt shipping taxt items.",
    isCompleted: true,
  },
  {
    status: "DEPARTED FACILITY",
    date: "Oct 25, 04:00 PM",
    description: "Departed Facility - Facahens, Oct 25, 01:16 PM, the item axen-arrived to trants, departed delivery tnmcrrarr and expoted delivery.",
    isCompleted: true,
  },
  {
    status: "ORDER PLACED",
    date: "Oct 23, 04:00 PM",
    description: "Your order placed - Oct 23, 04:00 PM in a goo:ar carrd processour.",
    isCompleted: true,
  },
];

const orderItems = [
  {
    name: "Leather Tote Bag",
    id: "1100001",
    qty: 1,
    price: 380.0,
    image: "https://images.unsplash.com/photo-1544816155-12df9643f363?q=80&w=200&h=200&auto=format&fit=crop",
  },
  {
    name: "Aviator Sunglasses",
    id: "1100202",
    qty: 1,
    price: 400.0,
    image: "https://images.unsplash.com/photo-1511499767390-a7335958beba?q=80&w=200&h=200&auto=format&fit=crop",
  },
  {
    name: "Printed Silk Scarf",
    id: "1100203",
    qty: 1,
    price: 290.0,
    image: "https://images.unsplash.com/photo-1606760227091-3dd870d97f1d?q=80&w=200&h=200&auto=format&fit=crop",
  },
];

export default function App() {
  return (
    <div className="min-h-screen p-6 md:p-12 lg:p-20 max-w-7xl mx-auto">
      {/* Header Section */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-gray-300 pb-12 mb-12">
        <div className="space-y-2">
          <h1 className="font-serif text-5xl md:text-7xl tracking-tight uppercase leading-none">
            Order #LX-8945-BT
          </h1>
          <h2 className="font-serif text-5xl md:text-7xl tracking-tight uppercase leading-none">
            Delivered
          </h2>
        </div>
        
        <div className="mt-8 md:mt-0 grid grid-cols-2 gap-x-12 gap-y-4 text-xs tracking-widest uppercase font-medium">
          <div>
            <p className="text-gray-500 mb-1">Estimated Delivery</p>
            <p className="font-serif text-3xl normal-case tracking-normal">Oct 26, 2024</p>
          </div>
          <div>
            <p className="text-gray-500 mb-1">Estimated Delivery</p>
            <p className="font-serif text-3xl normal-case tracking-normal">Oct 24-15</p>
          </div>
          <div className="col-span-1">
            <p className="text-gray-500">Estimated Delivery</p>
          </div>
          <div className="col-span-1">
            <p className="text-gray-500">Carrier: DHL Express (Priority)</p>
          </div>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-16">
        {/* Timeline Section */}
        <section className="lg:col-span-2">
          <div className="relative space-y-12 pl-12">
            {/* Vertical Line */}
            <div className="absolute left-[1.15rem] top-2 bottom-2 w-0.5 bg-brand-text" />
            
            {timelineEvents.map((event, index) => (
              <motion.div 
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="relative"
              >
                {/* Timeline Dot */}
                <div className="absolute -left-12 top-1.5 w-10 h-10 flex items-center justify-center">
                  <div className="w-6 h-6 rounded-full border-2 border-brand-text bg-brand-bg flex items-center justify-center">
                    <div className="w-3 h-3 rounded-full bg-brand-accent" />
                  </div>
                </div>
                
                <div className="space-y-1">
                  <h3 className="font-bold text-lg tracking-tight uppercase">
                    {event.status} – <span className="font-normal normal-case text-gray-600">{event.date}</span>
                  </h3>
                  <p className="text-gray-600 leading-relaxed max-w-xl">
                    {event.description}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Order Details Section */}
        <section className="space-y-8 border-l border-gray-300 pl-8 lg:pl-16">
          <h3 className="font-serif text-2xl">Order Details</h3>
          
          <div className="space-y-6">
            {orderItems.map((item, index) => (
              <div key={index} className="flex gap-4 group">
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
          </div>

          <div className="pt-8 border-t border-gray-300 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Subtotal</span>
              <span>$365.00</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Shipping</span>
              <span>$2.25</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Tax</span>
              <span>$0.00</span>
            </div>
            <div className="flex justify-between pt-4 font-bold text-lg">
              <span>Total</span>
              <span>$242.90</span>
            </div>
          </div>

          <div className="pt-8 space-y-4">
            <p className="text-sm text-gray-600">Payment DHL Terense Assessment</p>
            <a href="#" className="inline-flex items-center gap-1 font-bold border-b-2 border-brand-text pb-0.5 hover:text-brand-accent hover:border-brand-accent transition-colors">
              Need Help?
            </a>
          </div>
        </section>
      </main>
    </div>
  );
}
