import { Headset } from 'lucide-react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import LoginForm from './components/LoginForm';

export default function App() {
  return (
    <div className="min-h-screen w-full relative overflow-hidden">
      {/* Cinematic Background */}
      <div className="fixed inset-0 z-0">
        <img 
          alt="High-end fashion editorial" 
          className="w-full h-full object-cover filter brightness-[0.85]" 
          src="https://images.unsplash.com/photo-1490481651871-ab68de25d43d?q=80&w=2070&auto=format&fit=crop"
          referrerPolicy="no-referrer"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-background/40 to-transparent"></div>
      </div>

      <Header />

      <main className="relative z-10 min-h-screen w-full flex items-center justify-center p-4 md:p-10 lg:p-20">
        <div className="w-full max-w-[1200px] grid grid-cols-1 lg:grid-cols-12 gap-0 overflow-hidden rounded-lg editorial-shadow bg-surface-container-lowest/90 backdrop-blur-2xl">
          <Sidebar />
          <LoginForm />
        </div>
      </main>

      {/* Support Bubble */}
      <div className="fixed bottom-6 right-6 md:bottom-10 md:right-10 z-50">
        <button className="bg-surface-container-lowest border border-outline-variant/20 p-4 rounded-full editorial-shadow group hover:bg-secondary-fixed transition-colors shadow-lg">
          <Headset size={24} className="text-primary group-hover:text-on-secondary-fixed" />
        </button>
      </div>
    </div>
  );
}
