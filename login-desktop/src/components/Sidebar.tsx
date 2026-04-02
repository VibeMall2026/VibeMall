import { ShieldCheck, Sparkles } from 'lucide-react';
import { motion } from 'motion/react';

export default function Sidebar() {
  return (
    <div className="hidden lg:flex lg:col-span-5 relative flex-col justify-end p-12 bg-surface-container overflow-hidden">
      <div className="absolute inset-0 z-0 opacity-40">
        <img 
          alt="Luxury textile texture" 
          className="w-full h-full object-cover grayscale" 
          src="https://images.unsplash.com/photo-1550684848-fac1c5b4e853?q=80&w=2070&auto=format&fit=crop"
          referrerPolicy="no-referrer"
        />
      </div>
      
      <motion.div 
        initial={{ opacity: 0, x: -30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.3 }}
        className="relative z-10"
      >
        <h2 className="font-headline text-4xl mb-6 tracking-tight leading-none text-primary italic">
          The Digital<br />Atelier
        </h2>
        <p className="font-body text-sm text-on-surface-variant leading-relaxed mb-8 opacity-80 max-w-xs">
          Return to your curated space of craftsmanship and heritage.
        </p>
        
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <ShieldCheck size={16} className="text-secondary" />
            <span className="font-label uppercase text-[9px] tracking-widest text-on-surface">Authenticated Access</span>
          </div>
          <div className="flex items-center gap-3">
            <Sparkles size={16} className="text-secondary" />
            <span className="font-label uppercase text-[9px] tracking-widest text-on-surface">Member Exclusive</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
