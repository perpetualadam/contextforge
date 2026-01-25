import { NavLink } from 'react-router-dom';
import { 
  MessageSquare, 
  Search, 
  FolderUp, 
  Bot, 
  Settings,
  Sun,
  Moon,
  HelpCircle
} from 'lucide-react';
import { clsx } from 'clsx';
import { useTheme, useConnection } from '../../store';
import { StatusIndicator } from '../ui';

const navItems = [
  { path: '/chat', label: 'Chat', icon: MessageSquare },
  { path: '/query', label: 'Query', icon: Search },
  { path: '/ingest', label: 'Ingest', icon: FolderUp },
  { path: '/agents', label: 'Agents', icon: Bot },
];

export function Sidebar() {
  const { isDark, toggle } = useTheme();
  const { isOnline } = useConnection();

  return (
    <aside 
      className="fixed left-0 top-0 h-full w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col"
      role="navigation"
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center">
            <span className="text-white font-bold text-lg">CF</span>
          </div>
          <div>
            <h1 className="font-semibold text-gray-900 dark:text-gray-100">ContextForge</h1>
            <StatusIndicator 
              status={isOnline ? 'online' : 'offline'} 
              size="sm"
            />
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
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

      {/* Bottom Actions */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700 space-y-1">
        <NavLink
          to="/settings"
          className={({ isActive }) => clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
            isActive 
              ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
          )}
        >
          <Settings className="w-5 h-5" aria-hidden="true" />
          <span>Settings</span>
        </NavLink>

        <NavLink
          to="/help"
          className={({ isActive }) => clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
            isActive 
              ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
          )}
        >
          <HelpCircle className="w-5 h-5" aria-hidden="true" />
          <span>Help</span>
        </NavLink>

        <button
          onClick={toggle}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDark ? (
            <Sun className="w-5 h-5" aria-hidden="true" />
          ) : (
            <Moon className="w-5 h-5" aria-hidden="true" />
          )}
          <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
        </button>
      </div>
    </aside>
  );
}

