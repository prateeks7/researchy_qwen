import { useState } from 'react'
import { Plus, MessageSquare, Trash2, Search, BookOpen, LogOut, GitCompare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import type { Conversation, CompareSession } from '@/types'
import sidebarBg from '../../utils/backgrounds/sidebar.jpg'
import icon from '../../utils/backgrounds/Icon.png'

interface SidebarProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string) => void
  compareSessions: CompareSession[]
  activeCompareId: string | null
  onSelectCompare: (id: string) => void
  onNewCompare: () => void
  onDeleteCompare: (id: string) => void
  compareMode: boolean
  onToggleCompareMode: () => void
}

function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const hours = diff / (1000 * 60 * 60)
  if (hours < 1) return 'Just now'
  if (hours < 24) return `${Math.floor(hours)}h ago`
  const days = hours / 24
  if (days < 7) return `${Math.floor(days)}d ago`
  return date.toLocaleDateString()
}

function groupByDate(convs: Conversation[]) {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const groups: { label: string; items: Conversation[] }[] = []
  const todayItems = convs.filter((c) => c.createdAt.toDateString() === today.toDateString())
  const yesterdayItems = convs.filter((c) => c.createdAt.toDateString() === yesterday.toDateString())
  const olderItems = convs.filter(
    (c) =>
      c.createdAt.toDateString() !== today.toDateString() &&
      c.createdAt.toDateString() !== yesterday.toDateString(),
  )

  if (todayItems.length) groups.push({ label: 'Today', items: todayItems })
  if (yesterdayItems.length) groups.push({ label: 'Yesterday', items: yesterdayItems })
  if (olderItems.length) groups.push({ label: 'Earlier', items: olderItems })
  return groups
}

export function Sidebar({
  conversations, activeId, onSelect, onNewChat, onDelete,
  compareSessions, activeCompareId, onSelectCompare, onNewCompare, onDeleteCompare,
  compareMode, onToggleCompareMode,
}: SidebarProps) {
  const { user, logout } = useAuth()
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [hoveredCompareId, setHoveredCompareId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase()),
  )
  const groups = groupByDate(filtered)

  return (
    <aside
      className="relative flex flex-col w-[280px] min-w-[280px] h-full overflow-hidden border-r border-black/10"
      style={{
        backgroundImage: `url(${sidebarBg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="absolute inset-0 bg-transparent" />

      <div className="relative z-10 flex flex-col h-full">
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-black/10">
          <img src={icon} alt="Researchy Berg" className="w-8 h-8 rounded-full object-cover" />
          <div>
            <h1 className="text-black font-semibold text-sm leading-tight">Researchy Berg</h1>
            <p className="text-black/50 text-[10px] leading-tight">AI Research Assistant</p>
          </div>
        </div>

        {/* New Chat */}
        <div className="px-3 pt-3 pb-2">
          <button
            onClick={onNewChat}
            className={cn(
              'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium',
              'bg-black/10 hover:bg-black/20 text-black hover:text-black',
              'border border-black/15 hover:border-black/25 transition-all duration-150 group',
            )}
          >
            <Plus className="w-4 h-4 text-black/50 group-hover:text-black transition-colors" />
            New conversation
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-black/5 border border-black/10">
            <Search className="w-3.5 h-3.5 text-black/40 flex-shrink-0" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent text-black text-xs placeholder:text-black/35 outline-none"
            />
          </div>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-1">
          {groups.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-12 text-black/30">
              <BookOpen className="w-8 h-8" />
              <p className="text-xs">No conversations yet</p>
            </div>
          ) : (
            groups.map((group) => (
              <div key={group.label}>
                <p className="text-[10px] font-medium text-black/35 uppercase tracking-wider px-2 py-2">
                  {group.label}
                </p>
                <div className="space-y-0.5">
                  {group.items.map((conv) => (
                    <div
                      key={conv.id}
                      className="relative group"
                      onMouseEnter={() => setHoveredId(conv.id)}
                      onMouseLeave={() => setHoveredId(null)}
                    >
                      <button
                        onClick={() => onSelect(conv.id)}
                        className={cn(
                          'w-full text-left flex items-start gap-2.5 px-2.5 py-2.5 rounded-lg transition-all duration-100',
                          activeId === conv.id
                            ? 'bg-black/15 border border-black/20 text-black'
                            : 'hover:bg-black/8 text-black/65 hover:text-black border border-transparent',
                        )}
                      >
                        <MessageSquare
                          className={cn(
                            'w-3.5 h-3.5 mt-0.5 flex-shrink-0 transition-colors',
                            activeId === conv.id ? 'text-black/70' : 'text-black/35',
                          )}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate leading-tight">{conv.title}</p>
                          <p className="text-[10px] text-black/40 mt-0.5">
                            {formatRelativeTime(conv.createdAt)}
                          </p>
                        </div>
                      </button>

                      {(hoveredId === conv.id || activeId === conv.id) && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onDelete(conv.id) }}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-black/30 hover:text-red-500 hover:bg-black/10 transition-all"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Compare Models button */}
        <div className="px-3 py-2 border-t border-black/10">
          <button
            onClick={onToggleCompareMode}
            className={cn(
              'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
              'border group',
              compareMode
                ? 'bg-black/15 border-black/25 text-black'
                : 'bg-black/5 hover:bg-black/12 border-black/10 hover:border-black/20 text-black/60 hover:text-black',
            )}
          >
            <GitCompare className="w-4 h-4 flex-shrink-0" />
            Compare Models
          </button>

          {/* Compare sessions list */}
          {compareSessions.length > 0 && (
            <div className="mt-2 space-y-0.5">
              <p className="text-[10px] font-medium text-black/35 uppercase tracking-wider px-1 py-1">
                Compare sessions
              </p>
              {compareSessions.slice(0, 5).map((cs) => (
                <div
                  key={cs.session_id}
                  className="relative group"
                  onMouseEnter={() => setHoveredCompareId(cs.session_id)}
                  onMouseLeave={() => setHoveredCompareId(null)}
                >
                  <button
                    onClick={() => { onSelectCompare(cs.session_id); if (!compareMode) onToggleCompareMode() }}
                    className={cn(
                      'w-full text-left flex items-start gap-2 px-2 py-2 rounded-lg transition-all duration-100',
                      activeCompareId === cs.session_id && compareMode
                        ? 'bg-black/15 border border-black/20 text-black'
                        : 'hover:bg-black/8 text-black/55 hover:text-black border border-transparent',
                    )}
                  >
                    <GitCompare className="w-3 h-3 mt-0.5 flex-shrink-0 text-black/35" />
                    <p className="text-[11px] truncate">{cs.title}</p>
                  </button>
                  {(hoveredCompareId === cs.session_id) && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onDeleteCompare(cs.session_id) }}
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-black/25 hover:text-red-500 hover:bg-black/8 transition-all"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* User footer */}
        <div className="px-3 py-3 border-t border-black/10">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-black/15 border border-black/20 flex items-center justify-center flex-shrink-0">
              <span className="text-black/60 text-[10px] font-semibold uppercase">
                {user?.email?.[0] ?? '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-black/70 text-xs font-medium truncate">{user?.email}</p>
              <p className="text-black/30 text-[10px]">Powered by Qwen · Berg</p>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="p-1.5 rounded-md text-black/30 hover:text-black/60 hover:bg-black/10 transition-all flex-shrink-0"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}
