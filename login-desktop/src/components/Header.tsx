import { Search, ShoppingBag } from 'lucide-react';
import { motion } from 'motion/react';

export default function Header() {
  return (
    <header className="fixed top-0 w-full z-50 flex justify-between items-center px-6 md:px-12 py-6 md:py-8 pointer-events-none">
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="pointer-events-auto"
      >
        <span className="text-2xl md:text-3xl font-headline italic tracking-tighter text-on-background">VIBEMALL</span>
      </motion.div>
      
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="pointer-events-auto flex items-center gap-4 md:gap-8"
      >
        <div className="flex items-center gap-4 md:gap-6">
          <button className="text-on-background hover:opacity-70 transition-opacity">
            <Search size={20} strokeWidth={1.5} />
          </button>
          <button className="text-on-background hover:opacity-70 transition-opacity">
            <ShoppingBag size={20} strokeWidth={1.5} />
          </button>
        </div>
        <a 
          href="#" 
          className="hidden sm:block font-label uppercase text-[10px] tracking-[0.2rem] text-on-background hover:opacity-70 transition-opacity"
        >
          Return to Atelier
        </a>
      </motion.div>
    </header>
  );
}
