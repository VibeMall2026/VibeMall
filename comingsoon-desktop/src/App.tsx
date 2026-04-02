/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { motion } from 'motion/react';
import { ArrowRight } from 'lucide-react';

export default function App() {
  const [email, setEmail] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    alert(`Thank you! We'll notify you at ${email}`);
    setEmail('');
  };

  return (
    <main className="relative min-h-screen flex flex-col items-center justify-between selection:bg-secondary selection:text-white">
      {/* Hero Background Section */}
      <div className="absolute inset-0 z-0 overflow-hidden">
        <motion.img 
          initial={{ scale: 1.1, opacity: 0 }}
          animate={{ scale: 1, opacity: 0.3 }}
          transition={{ duration: 2, ease: "easeOut" }}
          className="w-full h-full object-cover grayscale filter contrast-125" 
          src="https://lh3.googleusercontent.com/aida-public/AB6AXuCwxPJ5X0YU9hHkR0VlL87uEw4RugJgBsqZyNb2aywYnpR9-3TT1KfL1fmbg0Zm-30RLAwD7-ZbPwGliVgthbfVFl_RL6DvPWeqhrdmoT5O53Xi6NOzDWOXO_cWz0nY8c9rGB25CMYVurqjbGKPiOScxhNi1g7pA_end2uBHguaBtRhW5Gvn6m35L9mlQZBDMliHljU4GHvbjUaYucY-reP4mfB54oOtY-kkJeZy4NJPa-IQA9s7Xm1yeL8GASmgkUTWUJDldaKTUI"
          alt="Atmospheric silk fabric"
          referrerPolicy="no-referrer"
        />
        <div className="absolute inset-0 editorial-gradient"></div>
      </div>

      {/* Brand Header */}
      <header className="relative z-10 w-full pt-16 flex justify-center">
        <motion.h1 
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="font-serif text-3xl font-bold tracking-tighter text-primary"
        >
          VIBEMALL
        </motion.h1>
      </header>

      {/* Main Content */}
      <section className="relative z-10 flex flex-col items-center text-center px-6 max-w-4xl mx-auto py-12 md:py-24">
        <motion.h2 
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 1, delay: 0.4 }}
          className="font-serif text-5xl md:text-7xl lg:text-8xl text-primary leading-tight letter-spacing-vogue mb-8"
        >
          A New Era of Artistry <br className="hidden md:block"/> is Arriving
        </motion.h2>
        
        <motion.p 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 1, delay: 0.6 }}
          className="font-sans text-lg md:text-xl text-on-surface/70 max-w-2xl mx-auto leading-relaxed mb-16"
        >
          We are curating a collection that redefines the boundaries of modern craft. Be the first to witness the unveiling.
        </motion.p>

        {/* Notify Me Panel */}
        <motion.div 
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 1, delay: 0.8 }}
          className="glass-panel p-8 md:p-12 w-full max-w-xl flex flex-col items-center shadow-2xl shadow-black/5"
        >
          <span className="font-sans text-[10px] uppercase letter-spacing-label text-secondary mb-6 block font-semibold">
            Join the Private Viewing
          </span>
          <form onSubmit={handleSubmit} className="w-full flex flex-col md:flex-row gap-4">
            <div className="relative flex-grow">
              <input 
                required
                className="w-full bg-surface border border-primary/10 px-6 py-4 font-sans text-xs letter-spacing-label focus:outline-none focus:border-secondary transition-all duration-300 placeholder:text-on-surface/30"
                placeholder="ENTER YOUR EMAIL"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <button 
              className="bg-primary text-white px-10 py-4 font-sans text-xs uppercase tracking-widest hover:bg-primary/90 transition-all duration-300 flex items-center justify-center group"
              type="submit"
            >
              Notify Me
              <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </form>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 w-full border-t border-primary/5 bg-surface/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-8 md:px-16 py-12 flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="font-serif text-lg font-bold text-primary">
            VIBEMALL
          </div>
          
          <div className="flex flex-wrap justify-center gap-8 md:gap-12">
            <a className="font-sans text-[10px] tracking-widest uppercase text-on-surface/50 hover:text-secondary transition-colors duration-300" href="#">Privacy Policy</a>
            <a className="font-sans text-[10px] tracking-widest uppercase text-on-surface/50 hover:text-secondary transition-colors duration-300" href="#">Terms of Service</a>
            <a className="font-sans text-[10px] tracking-widest uppercase text-on-surface/50 hover:text-secondary transition-colors duration-300" href="#">Contact Us</a>
          </div>

          <div className="font-sans text-[10px] tracking-widest uppercase text-on-surface/40">
            © 2024 VibeMall Atelier. All rights reserved.
          </div>
        </div>
      </footer>

      {/* Aesthetic Decorative Elements */}
      <div className="fixed top-0 left-0 w-full h-1 bg-gradient-to-r from-secondary to-transparent z-50"></div>
      <div className="fixed bottom-0 right-0 p-12 z-0 opacity-5 pointer-events-none hidden lg:block">
        <span className="font-serif text-[24rem] text-primary italic leading-none select-none">V</span>
      </div>
    </main>
  );
}
