import { 
  Package, 
  Calendar, 
  Headphones, 
  Check, 
  ChevronRight 
} from 'lucide-react';
import { motion } from 'motion/react';

const STEPS = [
  { label: 'Ordered', status: 'completed' },
  { label: 'Processing', status: 'completed' },
  { label: 'Shipped', status: 'completed' },
  { label: 'Out for Delivery', status: 'pending' },
  { label: 'Delivered', status: 'pending' },
];

const ITEMS = [
  {
    id: 1,
    name: 'Gucci Jackie 1961 Small Shoulder Bag',
    qty: 1,
    image: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&q=80&w=400',
  },
  {
    id: 2,
    name: 'Saint Laurent Tribute Sandals',
    qty: 1,
    image: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?auto=format&fit=crop&q=80&w=400',
  },
  {
    id: 3,
    name: 'Burberry Classic Check Scarf',
    qty: 1,
    image: 'https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?auto=format&fit=crop&q=80&w=400',
  },
];

export default function App() {
  return (
    <div className="min-h-screen font-sans p-6 max-w-md mx-auto">
      {/* Header / Stepper */}
      <div className="mb-10 pt-4">
        <div className="flex justify-between items-center relative mb-2">
          {/* Progress Line Background */}
          <div className="absolute top-1/2 left-0 w-full h-[2px] bg-gray-200 -translate-y-1/2 z-0" />
          
          {/* Active Progress Line */}
          <div 
            className="absolute top-1/2 left-0 h-[2px] bg-luxury-gold -translate-y-1/2 z-0 transition-all duration-500" 
            style={{ width: '50%' }}
          />

          {STEPS.map((step, idx) => (
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
          {STEPS.map((step, idx) => (
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
        Order #LX-88429
      </motion.h1>

      {/* Info Cards */}
      <div className="space-y-4 mb-10">
        <InfoCard 
          icon={<Package className="text-gray-900" size={24} />}
          title="Latest Update"
          description="In Transit - Arrived at regional facility, Paris, FR. Oct 25, 10:30 AM"
          delay={0.1}
        />
        <InfoCard 
          icon={<Calendar className="text-gray-900" size={24} />}
          title="Estimated Delivery"
          description="Friday, October 27th - Monday, October 30th"
          delay={0.2}
        />
        <InfoCard 
          icon={<Headphones className="text-gray-900" size={24} />}
          title="Help & Support"
          description="Contact Concierge"
          isAction
          delay={0.3}
        />
      </div>

      {/* Items Section */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-4">Items in your shipment</h2>
        <div className="flex overflow-x-auto pb-4 gap-4 no-scrollbar">
          {ITEMS.map((item, idx) => (
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
              <p className="text-sm text-gray-500">Qty: {item.qty}</p>
            </motion.div>
          ))}
        </div>
      </div>
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

