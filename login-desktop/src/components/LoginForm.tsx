import { useState } from 'react';
import { Eye, EyeOff, ArrowRight } from 'lucide-react';
import { motion } from 'motion/react';

export default function LoginForm() {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="lg:col-span-7 p-8 md:p-12 lg:p-20 h-auto lg:h-[800px] flex items-center">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="max-w-[460px] mx-auto w-full"
      >
        <header className="mb-12">
          <span className="font-label uppercase text-[10px] tracking-[0.3rem] text-secondary mb-4 block">Welcome Back</span>
          <h1 className="font-headline text-4xl md:text-5xl tracking-tighter text-on-background mb-4">Atelier Access</h1>
          <p className="text-on-surface-variant text-sm font-body">
            New to the Atelier? <a className="text-primary font-bold underline underline-offset-4 decoration-secondary" href="#">Create an Account</a>
          </p>
        </header>

        <form className="space-y-10" onSubmit={(e) => e.preventDefault()}>
          {/* Email Address */}
          <div className="relative">
            <label className="font-label uppercase text-[10px] tracking-widest text-on-surface-variant mb-2 block" htmlFor="email">
              Email Address
            </label>
            <input 
              className="w-full bg-surface-container-low border-0 border-b border-outline-variant/30 focus:border-primary focus:ring-0 px-0 py-3 text-sm transition-colors placeholder:text-outline-variant/50" 
              id="email" 
              placeholder="name@atelier.com" 
              required 
              type="email"
            />
          </div>

          {/* Password */}
          <div className="relative">
            <div className="flex justify-between items-baseline mb-2">
              <label className="font-label uppercase text-[10px] tracking-widest text-on-surface-variant block" htmlFor="password">
                Password
              </label>
              <a className="text-[9px] uppercase tracking-widest text-secondary hover:text-primary transition-colors" href="#">
                Forgot Password?
              </a>
            </div>
            <div className="relative">
              <input 
                className="w-full bg-surface-container-low border-0 border-b border-outline-variant/30 focus:border-primary focus:ring-0 px-0 py-3 text-sm transition-colors" 
                id="password" 
                placeholder="••••••••" 
                required 
                type={showPassword ? "text" : "password"}
              />
              <button 
                className="absolute right-0 top-1/2 -translate-y-1/2 text-on-surface-variant/60 hover:text-primary transition-colors" 
                type="button"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Remember Me */}
          <div className="flex items-center gap-3">
            <input 
              className="h-4 w-4 rounded border-outline-variant text-primary focus:ring-secondary cursor-pointer" 
              id="remember" 
              name="remember" 
              type="checkbox"
            />
            <label className="font-label uppercase text-[10px] tracking-widest text-on-surface-variant cursor-pointer" htmlFor="remember">
              Remember Me
            </label>
          </div>

          {/* Actions */}
          <div className="space-y-6 pt-4">
            <button 
              className="w-full group bg-primary text-on-primary py-5 rounded-md font-label uppercase text-xs tracking-[0.2em] hover:bg-primary-container transition-all flex items-center justify-center gap-3 overflow-hidden relative" 
              type="submit"
            >
              <span className="relative z-10">Sign In</span>
              <ArrowRight size={16} className="relative z-10 transition-transform group-hover:translate-x-1" />
            </button>

            <div className="relative flex items-center py-2">
              <div className="flex-grow border-t border-outline-variant/20"></div>
              <span className="flex-shrink mx-4 font-label uppercase text-[9px] tracking-widest text-outline">or</span>
              <div className="flex-grow border-t border-outline-variant/20"></div>
            </div>

            <button 
              className="w-full border border-outline-variant/30 hover:border-primary hover:bg-surface-container-low py-4 px-6 font-label text-[10px] uppercase tracking-[0.15em] text-primary transition-all duration-300 flex items-center justify-center gap-3" 
              type="button"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"></path>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"></path>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"></path>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"></path>
              </svg>
              <span>Login with Google</span>
            </button>
          </div>
        </form>

        <footer className="mt-16 pt-8 border-t border-outline-variant/10 text-center">
          <p className="font-label uppercase text-[9px] tracking-widest text-outline">© 2024 VIBEMALL ATELIER • ALL RIGHTS RESERVED.</p>
        </footer>
      </motion.div>
    </div>
  );
}
