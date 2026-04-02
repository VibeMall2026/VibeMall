/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Search, ShoppingBag, Eye } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';

export default function App() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <div className="min-h-screen bg-background selection:bg-secondary/20">
      {/* Background Imagery */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none opacity-30">
        <div className="absolute top-[10%] right-[-5%] w-[400px] h-[600px]">
          <img 
            className="w-full h-full object-cover grayscale brightness-110" 
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuDwbxkAtIv-uszZjkYayOBD6eXLf9xulz0g1RGwj4EeeZeipQgL_eJA9bgRE6sKTbeXmCC2V9Z9l9g2hFm-rLu1LyuB-geI_Ggjq69eFvTE24f3zpfrmogEdqUoa1WnNYQ5you1pKEruyRbq1KZpEEbu_Z22BrbyBTew_K7mXlSy_2s86VR2ti86gvK2P4Z9hi2SuKsnfMGjiDdVgIyxBUgBRPsEvJUKe6SY93WPm9lEQIYg0bquhuZjaufIIZc9Ta87Kj_0IhhRJU" 
            alt="Editorial fashion"
            referrerPolicy="no-referrer"
          />
        </div>
        <div className="absolute bottom-[5%] left-[-5%] w-[300px] h-[450px]">
          <img 
            className="w-full h-full object-cover grayscale contrast-75" 
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuD3wXjDANVI_xsgwkhSUzCyHiNtfoLkIZzMq27Nuw3lLiZkzpi-7u0yfhS47K1uA-ckBHeg_sSlRykBhFyy_u_mqd4jZApEQMR5sHmhq2caIIBUHG75NVmCtx2emZS4Tgg6iOpv965WFh5k5SsbGb4MGV7CcdnTNzKKKHZDIFBJIvGPqttRopOz29zGoxWlrF51CRI3RnAXf3TCzPU7WUh4D6bOlL7m7tRPAKSO26e6CucQejzbkh7d3FKjnkCtWyYspdbIe2zU5II" 
            alt="Textile detail"
            referrerPolicy="no-referrer"
          />
        </div>
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-xl flex justify-between items-center px-8 md:px-16 py-6">
        <div className="flex items-center gap-8">
          <span className="text-2xl font-bold tracking-tighter text-primary font-headline">VIBEMALL</span>
          <div className="hidden md:flex gap-6">
            <span className="text-[10px] uppercase tracking-[0.2em] text-primary/60 font-headline cursor-pointer hover:text-primary transition-colors">Collections</span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-primary/60 font-headline cursor-pointer hover:text-primary transition-colors">Atelier</span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-primary/60 font-headline cursor-pointer hover:text-primary transition-colors">Stories</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <Search className="w-5 h-5 text-primary cursor-pointer stroke-[1.5px]" />
          <ShoppingBag className="w-5 h-5 text-primary cursor-pointer stroke-[1.5px]" />
        </div>
      </nav>

      {/* Main Content */}
      <main className="min-h-screen flex items-center justify-center pt-24 pb-12 px-8">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-[540px] bg-white/80 backdrop-blur-md p-10 md:p-16 rounded-sm shadow-[0_40px_60px_-5px_rgba(27,28,25,0.04)] border border-outline/10"
        >
          <div className="text-center mb-12">
            <span className="logo-text text-3xl font-bold tracking-tighter text-primary mb-6 block uppercase">VIBEMALL</span>
            <h1 className="text-4xl md:text-5xl font-bold text-primary tracking-tight mb-4">Welcome Back</h1>
            <p className="text-outline font-light text-sm tracking-wide">Enter your details to access your private viewing.</p>
          </div>

          <form className="space-y-8" onSubmit={(e) => e.preventDefault()}>
            {/* Email Input */}
            <div className="space-y-2">
              <label className="block text-[10px] tracking-[0.2em] uppercase font-semibold text-secondary">Email Address</label>
              <input 
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-transparent border-b border-outline/30 px-0 py-3 focus:outline-none focus:border-secondary transition-colors duration-500 placeholder:text-outline/40 font-body text-sm"
                placeholder="atelier@vibemall.com"
              />
            </div>

            {/* Password Input */}
            <div className="space-y-2">
              <div className="flex justify-between items-end">
                <label className="block text-[10px] tracking-[0.2em] uppercase font-semibold text-secondary">Password</label>
                <button type="button" className="text-[10px] tracking-[0.2em] uppercase text-outline hover:text-primary transition-colors flex items-center gap-1">
                  <Eye className="w-3 h-3" /> Show
                </button>
              </div>
              <input 
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-transparent border-b border-outline/30 px-0 py-3 focus:outline-none focus:border-secondary transition-colors duration-500 placeholder:text-outline/40 font-body text-sm"
                placeholder="••••••••••••"
              />
            </div>

            {/* Remember & Forgot */}
            <div className="flex items-center justify-between text-xs tracking-wide">
              <label className="flex items-center gap-2 cursor-pointer group">
                <input type="checkbox" className="rounded-none border-outline/30 text-primary focus:ring-0 w-4 h-4 transition-all" />
                <span className="text-outline group-hover:text-primary transition-colors">Remember Me</span>
              </label>
              <a href="#" className="text-secondary hover:text-primary transition-colors font-medium">Forgot Password?</a>
            </div>

            {/* Sign In Button */}
            <button 
              type="submit"
              className="w-full bg-primary text-white py-5 px-8 font-body text-[11px] tracking-[0.3em] uppercase font-bold hover:bg-primary/90 transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] scale-100 hover:scale-[1.01] active:scale-95"
            >
              SIGN IN
            </button>
          </form>

          {/* Social Login */}
          <div className="mt-12 space-y-8">
            <div className="relative flex items-center justify-center">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-outline/20"></div>
              </div>
              <span className="relative bg-white/0 px-4 text-[10px] tracking-[0.2em] uppercase text-outline">Or Continue With</span>
            </div>

            <button className="w-full flex items-center justify-center gap-3 bg-[#f5f3ee] border border-outline/10 py-4 px-8 text-[11px] tracking-[0.2em] uppercase font-semibold hover:bg-[#eae8e3] transition-colors duration-500 group">
              <svg className="w-4 h-4 grayscale group-hover:grayscale-0 transition-all" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"></path>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"></path>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"></path>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"></path>
              </svg>
              Google
            </button>
          </div>

          {/* Footer Link */}
          <div className="mt-12 text-center">
            <p className="text-xs tracking-wide text-outline">
              New to the Atelier? 
              <a href="#" className="text-primary font-bold hover:text-secondary transition-colors ml-2 underline underline-offset-8 decoration-1 decoration-secondary/30">Create an Account</a>
            </p>
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="w-full py-12 px-16 bg-[#f0eee9] flex flex-col md:flex-row justify-between items-center gap-8">
        <div className="font-body text-[10px] tracking-[0.2em] uppercase text-primary opacity-70">
          © 2024 VIBEMALL ATELIER. ALL RIGHTS RESERVED.
        </div>
        <div className="flex gap-10 font-body text-[10px] tracking-[0.2em] uppercase text-primary">
          <a href="#" className="opacity-70 hover:opacity-100 transition-opacity">Privacy Policy</a>
          <a href="#" className="opacity-70 hover:opacity-100 transition-opacity">Terms of Service</a>
          <a href="#" className="opacity-70 hover:opacity-100 transition-opacity">Shipping & Returns</a>
        </div>
      </footer>
    </div>
  );
}
