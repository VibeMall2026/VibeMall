import { useEffect, useState, type FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, ArrowRight, CheckCircle2, Home, Search, User, Bell } from 'lucide-react';

function getCookie(name: string): string {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop()?.split(';').shift() || '';
  }
  return '';
}

export default function App() {
  const [email, setEmail] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [launchDate, setLaunchDate] = useState('2026');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let cancelled = false;

    const fetchLaunchDate = async () => {
      try {
        const response = await fetch('/coming-soon/', { credentials: 'include' });
        if (!response.ok) return;
        const html = await response.text();
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const dateNode = doc.querySelector('.launch-date');
        const parsed = dateNode?.textContent?.trim();
        if (!cancelled && parsed) {
          setLaunchDate(parsed);
        }
      } catch {
        // Keep fallback date when the source page is unavailable.
      }
    };

    fetchLaunchDate();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    if (email) {
      setIsSubmitting(true);
      const csrfToken = getCookie('csrftoken');

      try {
        const payload = new URLSearchParams({
          email: email.trim(),
          source_page: 'ComingSoonMobile',
          csrfmiddlewaretoken: csrfToken || '',
        });

        const response = await fetch('/newsletter/subscribe/', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken,
          },
          body: payload.toString(),
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.message || 'Subscription failed');
        }

        setIsSubmitted(true);
        setEmail('');
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : 'Unable to subscribe right now.');
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  return (
    <main className="relative min-h-screen w-full flex flex-col items-center justify-between px-8 py-16 pt-24 pb-28 silk-texture overflow-hidden selection:bg-secondary/20">
      {/* Background Aesthetic Elements */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-[#fadfb1] opacity-20 blur-[100px] rounded-full" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-[#ffdad9] opacity-10 blur-[100px] rounded-full" />
        
        {/* Asymmetric Editorial Image Detail */}
        <motion.div 
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 0.6, x: 0 }}
          transition={{ duration: 1.5, ease: "easeOut" }}
          className="absolute top-1/2 -right-16 -translate-y-1/2 w-48 h-72 mix-blend-multiply"
        >
          <img 
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuDjMcdqIKq_vE8fqOFlUzMeeexd5rld_DVqipLjG_6OA7N-GGykbKiXVXnApLxrw8SUHzyapS0zXs2ROzl5JmTeo_qEKXwR_wx7HM7TLrazUXh5vvJey5awHS0l-in0tjOJKkLGjXhj3vOv2n-HF9JfcyBO2IncppRwqvVI5a0bSp1KcdvdvWxQ_edYIDw5EhyKseNdXK9zCAURRyzUd9UsFh0X4yacCQKazMTjw6lrnnyjLJGoFrJp6Y4LpXS-Zp7UyrKt0hPI6c0" 
            alt="Silk texture" 
            className="w-full h-full object-cover grayscale sepia-[0.3]"
            referrerPolicy="no-referrer"
          />
        </motion.div>
      </div>

      {/* Header: Logo */}
      <header className="w-full flex justify-center z-10 fixed top-0 left-0 py-5 bg-surface/85 backdrop-blur-lg border-b border-outline-variant/20">
        <motion.h1 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="font-headline text-2xl font-bold tracking-[0.3em] text-primary"
        >
          VIBEMALL
        </motion.h1>
      </header>

      {/* Centered Hero & CTA Section */}
      <section className="flex flex-col items-center text-center max-w-md w-full z-10">
        {/* Decorative Icon */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 0.4, scale: 1 }}
          transition={{ duration: 1, delay: 0.2 }}
          className="mb-8"
        >
          <Sparkles className="w-10 h-10 text-primary" />
        </motion.div>

        {/* Headline */}
        <motion.h2 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="font-headline text-4xl md:text-5xl font-light text-primary leading-tight mb-6"
        >
          A New Era of Artistry is Arriving
        </motion.h2>

        {/* Subtext */}
        <motion.p 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          className="font-body text-on-surface-variant text-sm md:text-base leading-relaxed mb-12 max-w-xs md:max-w-sm tracking-wide"
        >
          We are curating a collection that redefines the boundaries of modern craft. Be the first to witness the unveiling.
        </motion.p>

        <p className="font-label text-[10px] tracking-[0.2rem] uppercase text-secondary mb-6">Launch Window: {launchDate}</p>

        {/* Subscription Form Box */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.8 }}
          className="w-full bg-surface-container-lowest/50 backdrop-blur-md p-2 rounded-xl shadow-[0_40px_60px_-5px_rgba(27,28,25,0.04)] border border-outline-variant/10"
        >
          <AnimatePresence mode="wait">
            {!isSubmitted ? (
              <motion.form 
                key="form"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0, y: -20 }}
                onSubmit={handleSubmit}
                className="flex flex-col gap-2"
              >
                <div className="relative">
                  <input 
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-surface-container-low border-none rounded-lg px-6 py-5 text-xs font-medium tracking-[0.1rem] text-primary placeholder:text-on-surface-variant/40 focus:ring-1 focus:ring-secondary/20 transition-all duration-300 outline-none"
                    placeholder="ENTER YOUR EMAIL"
                    required
                  />
                </div>
                <button 
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-primary text-on-primary py-5 rounded-lg font-medium text-xs tracking-[0.15rem] flex items-center justify-center gap-3 hover:bg-[#2c2c2c] transition-all duration-300 group"
                >
                  {isSubmitting ? 'SENDING...' : 'NOTIFY ME'}
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
              </motion.form>
            ) : (
              <motion.div 
                key="success"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="py-10 flex flex-col items-center gap-4"
              >
                <CheckCircle2 className="w-12 h-12 text-secondary" />
                <p className="font-headline text-lg text-primary">Thank you for joining us.</p>
                <p className="text-xs tracking-widest text-on-surface-variant uppercase">We'll be in touch soon.</p>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
        {errorMessage && <p className="mt-4 text-xs text-red-700 tracking-wide">{errorMessage}</p>}
      </section>

      {/* Footer Visual/Status */}
      <footer className="z-10 text-center">
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.3 }}
          transition={{ duration: 1, delay: 1 }}
          className="flex items-center justify-center gap-6 text-xs font-medium tracking-[0.2em] uppercase"
        >
          <span>EST 2024</span>
          <span className="w-1 h-1 bg-primary rounded-full" />
          <span>BENGALURU</span>
        </motion.div>
      </footer>

      <div className="fixed bottom-0 left-0 right-0 z-30 bg-surface-container-lowest/95 backdrop-blur-xl border-t border-outline-variant/20 px-4 py-3">
        <div className="max-w-sm mx-auto flex items-center justify-between">
          <a href="/" className="flex flex-col items-center gap-1 text-on-surface-variant text-[10px] tracking-wide">
            <Home className="w-5 h-5" />
            Home
          </a>
          <a href="/shop/" className="flex flex-col items-center gap-1 text-on-surface-variant text-[10px] tracking-wide">
            <Search className="w-5 h-5" />
            Shop
          </a>
          <a href="/coming-soon/" className="flex flex-col items-center gap-1 text-primary text-[10px] tracking-wide font-semibold">
            <Bell className="w-5 h-5" />
            Launch
          </a>
          <a href="/profile/" className="flex flex-col items-center gap-1 text-on-surface-variant text-[10px] tracking-wide">
            <User className="w-5 h-5" />
            Profile
          </a>
        </div>
      </div>
    </main>
  );
}
