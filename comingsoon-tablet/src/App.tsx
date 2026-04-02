import { useState, FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

export default function App() {
  const [email, setEmail] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (email) {
      setIsSubmitted(true);
      setEmail('');
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden selection:bg-secondary/20">
      {/* Texture Overlay */}
      <div className="fixed inset-0 pointer-events-none silk-texture z-0" />
      
      {/* Visual Polish: Soft Radial Background Gradient */}
      <div className="fixed inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(111,92,55,0.05),transparent_70%)] pointer-events-none z-0" />

      <main className="relative z-10 min-h-screen flex flex-col items-center justify-center px-6 md:px-24 py-20">
        {/* Brand Identity Section */}
        <header className="absolute top-12 md:top-16 w-full flex justify-center">
          <motion.h1 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            className="font-headline text-2xl font-bold tracking-tighter text-primary"
          >
            VibeMall
          </motion.h1>
        </header>

        {/* Hero Canvas */}
        <div className="max-w-3xl w-full text-center space-y-12">
          {/* Headline Cluster */}
          <div className="space-y-6">
            <motion.span 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.8 }}
              className="font-label text-xs tracking-[0.2rem] uppercase text-secondary font-medium block"
            >
              Artisanal Heritage
            </motion.span>
            
            <motion.h2 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.8 }}
              className="font-headline text-5xl md:text-7xl leading-[1.1] tracking-tight text-primary"
            >
              A New Era of Artistry is Arriving
            </motion.h2>
            
            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6, duration: 0.8 }}
              className="font-body text-lg md:text-xl text-on-surface-variant max-w-xl mx-auto leading-relaxed"
            >
              We are curating a collection that redefines the boundaries of modern craft. Be the first to witness the unveiling.
            </motion.p>
          </div>

          {/* Subscription Journey */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.8, duration: 0.8 }}
            className="flex justify-center pt-4"
          >
            <div className="w-full max-w-md p-2 bg-surface-container-low rounded-xl editorial-shadow">
              <AnimatePresence mode="wait">
                {!isSubmitted ? (
                  <motion.form 
                    key="form"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, y: -10 }}
                    onSubmit={handleSubmit}
                    className="flex flex-col md:flex-row gap-2"
                  >
                    <input 
                      className="flex-grow bg-surface-container-lowest border-none focus:ring-1 focus:ring-secondary/30 font-label text-xs tracking-[0.1rem] px-6 py-4 rounded-lg placeholder:text-on-surface-variant/40 outline-none transition-all"
                      placeholder="ENTER YOUR EMAIL"
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                    <button 
                      type="submit"
                      className="bg-primary text-white font-label text-xs tracking-[0.1rem] px-8 py-4 rounded-lg transition-all duration-500 hover:bg-primary/90 flex items-center justify-center gap-2 group whitespace-nowrap"
                    >
                      NOTIFY ME 
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </button>
                  </motion.form>
                ) : (
                  <motion.div 
                    key="success"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center justify-center gap-3 py-4 text-secondary font-label text-xs tracking-[0.1rem] uppercase font-medium"
                  >
                    <CheckCircle2 className="w-5 h-5" />
                    Thank you. We'll be in touch.
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </div>

        {/* Aesthetic Detail: Floating Elements (Desktop Only) */}
        <motion.div 
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 0.4, x: 0 }}
          transition={{ delay: 1, duration: 1.2 }}
          className="absolute left-12 bottom-24 hidden xl:block"
        >
          <div className="w-48 h-64 bg-surface-variant rounded-sm overflow-hidden grayscale hover:grayscale-0 transition-all duration-700 cursor-crosshair">
            <img 
              alt="Material Study" 
              className="w-full h-full object-cover mix-blend-multiply" 
              src="https://images.unsplash.com/photo-1528459801416-a9e53bbf4e17?auto=format&fit=crop&q=80&w=800"
              referrerPolicy="no-referrer"
            />
          </div>
          <p className="font-label text-[10px] tracking-widest uppercase mt-4 text-secondary">Material Study 01</p>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 0.4, x: 0 }}
          transition={{ delay: 1.2, duration: 1.2 }}
          className="absolute right-12 top-48 hidden xl:block"
        >
          <div className="w-32 h-48 bg-surface-variant rounded-sm overflow-hidden grayscale hover:grayscale-0 transition-all duration-700 cursor-crosshair">
            <img 
              alt="Curated Essence" 
              className="w-full h-full object-cover mix-blend-multiply" 
              src="https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&q=80&w=800"
              referrerPolicy="no-referrer"
            />
          </div>
          <p className="font-label text-[10px] tracking-widest uppercase mt-4 text-secondary text-right">Curated Essence</p>
        </motion.div>

        {/* Footer Note */}
        <footer className="absolute bottom-12 w-full text-center">
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.6 }}
            transition={{ delay: 1.5, duration: 1 }}
            className="flex items-center justify-center gap-8 font-label text-[10px] tracking-[0.15rem] text-on-surface-variant uppercase"
          >
            <span>EST. 2024</span>
            <span className="w-1 h-1 bg-secondary rounded-full" />
            <span>COMING SOON</span>
          </motion.div>
        </footer>
      </main>
    </div>
  );
}
