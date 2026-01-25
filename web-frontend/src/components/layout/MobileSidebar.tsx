import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { 
  Menu, 
  X,
  MessageSquare, 
  Search, 
  FolderUp, 
  Bot, 
  Settings,
  Sun,
  Moon,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useTheme, useConnection } from '../../store';
import { StatusIndicator } from '../ui';

const navItems = [
  { path: '/chat', label: 'Chat', icon: MessageSquare },
  { path: '/query', label: 'Query', icon: Search },
  { path: '/ingest', label: 'Ingest', icon: FolderUp },
  { path: '/agents', label: 'Agents', icon: Bot },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export function MobileSidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const { isDark, toggle } = useTheme();
  const { isOnline } = useConnection();

  const closeSidebar = () => setIsOpen(false);

  return (
    <>
      {/* Mobile Header */}
      <header className="fixed top-0 left-0 right-0 h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 z-30 flex items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsOpen(true)}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Open menu"
            aria-expanded={isOpen}
            aria-controls="mobile-sidebar"
          >
            <Menu className="w-6 h-6" aria-hidden="true" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">CF</span>
            </div>
            <span className="font-semibold text-gray-900 dark:text-gray-100">ContextForge</span>
          </div>
        </div>
        <StatusIndicator 
          status={isOnline ? 'online' : 'offline'} 
          showLabel={false}
          size="md"
        />
      </header>

      {/* Sidebar Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Panel */}
      <aside
        id="mobile-sidebar"
        className={clsx(
          'fixed top-0 left-0 h-full w-72 bg-white dark:bg-gray-800 z-50 transform transition-transform duration-300',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        aria-label="Mobile navigation"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-lg">CF</span>
            </div>
            <span className="font-semibold text-gray-900 dark:text-gray-100">ContextForge</span>
          </div>
          <button
            onClick={closeSidebar}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={closeSidebar}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-3 rounded-lg transition-colors',
                isActive 
                  ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              )}
            >
              <item.icon className="w-5 h-5" aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Theme Toggle */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={toggle}
            className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
          </button>
        </div>
      </aside>

      {/* Spacer for fixed header */}
      <div className="h-16" />
    </>
  );
}

