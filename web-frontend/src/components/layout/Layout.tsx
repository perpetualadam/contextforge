import { ReactNode, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { MobileSidebar } from './MobileSidebar';
import { ConnectionBanner } from '../ui';
import { useTheme, useConnection } from '../../store';
import apiClient from '../../api/client';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { isDark } = useTheme();
  const { isOnline, setOnline } = useConnection();

  // Apply theme to document
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  // Listen for connection changes
  useEffect(() => {
    const unsubscribe = apiClient.onConnectionChange(setOnline);
    return () => { unsubscribe(); };
  }, [setOnline]);

  const handleRetry = async () => {
    try {
      await apiClient.getHealth();
    } catch {
      // Will be handled by the client
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <ConnectionBanner isOnline={isOnline} onRetry={handleRetry} />
      
      {/* Desktop Sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile Sidebar */}
      <div className="lg:hidden">
        <MobileSidebar />
      </div>

      {/* Main Content */}
      <main 
        className="lg:ml-64 min-h-screen"
        id="main-content"
        role="main"
      >
        {children}
      </main>
    </div>
  );
}

