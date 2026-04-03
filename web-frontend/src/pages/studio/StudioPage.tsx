import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Layers,
  Bot,
  Code2,
  BookOpen,
  Hash,
  Workflow,
  Wand2,
  Terminal,
  Search,
  GitBranch,
} from 'lucide-react';
import { Card, CardContent } from '../../components/ui';
import { clsx } from 'clsx';

const tiles: { to: string; title: string; desc: string; icon: typeof LayoutDashboard }[] = [
  {
    to: '/studio/composer',
    title: 'Composer',
    desc: 'Multi-file agent session (poll until complete)',
    icon: Layers,
  },
  {
    to: '/studio/agent',
    title: 'Agent execute',
    desc: 'Plan and propose file changes from a task',
    icon: Bot,
  },
  {
    to: '/studio/code',
    title: 'Code tools',
    desc: 'Completion, inline edit, smart apply, multi-cursor',
    icon: Code2,
  },
  {
    to: '/studio/docs',
    title: 'Docs',
    desc: 'Index URLs and search documentation chunks',
    icon: BookOpen,
  },
  {
    to: '/studio/symbols',
    title: 'Symbols',
    desc: 'Definition and reference lookup',
    icon: Hash,
  },
  {
    to: '/studio/orchestrate',
    title: 'Orchestrate',
    desc: 'Repo-wide analysis pass',
    icon: Workflow,
  },
  {
    to: '/studio/prompts',
    title: 'Prompts',
    desc: 'Enhance prompts (LLM + context-aware)',
    icon: Wand2,
  },
  {
    to: '/studio/terminal',
    title: 'Terminal',
    desc: 'Run commands and suggest safe commands',
    icon: Terminal,
  },
  {
    to: '/studio/vector',
    title: 'Vector search',
    desc: 'Semantic search over the index',
    icon: Search,
  },
  {
    to: '/studio/git',
    title: 'Git',
    desc: 'Status, branch, log, diff, AI commit message (server repo)',
    icon: GitBranch,
  },
];

export function StudioPage() {
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-8 flex items-start gap-3">
        <LayoutDashboard className="w-8 h-8 text-primary-600 dark:text-primary-400 shrink-0 mt-1" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Studio</h1>
          <p className="text-gray-500 dark:text-gray-400 max-w-2xl">
            Gateway-backed tools that mirror the VS Code extension&apos;s API surface. Set repo path and
            project rules under Settings for agent, composer, orchestrate, and terminal cwd.
          </p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {tiles.map(({ to, title, desc, icon: Icon }) => (
          <NavLink key={to} to={to} className="group block">
            <Card
              className={clsx(
                'h-full transition-shadow border border-transparent',
                'hover:border-primary-200 dark:hover:border-primary-800 hover:shadow-md'
              )}
            >
              <CardContent className="p-5">
                <Icon className="w-6 h-6 text-primary-600 dark:text-primary-400 mb-3" aria-hidden />
                <h2 className="font-semibold text-gray-900 dark:text-gray-100 group-hover:text-primary-700 dark:group-hover:text-primary-300">
                  {title}
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{desc}</p>
              </CardContent>
            </Card>
          </NavLink>
        ))}
      </div>
    </div>
  );
}
