'use client'

import { useState, useCallback } from 'react'
import { ProjectSidebar } from '@/components/project-sidebar'
import { ChatWindow } from '@/components/chat-window'
import { MarkdownViewer } from '@/components/markdown-viewer'
import { ResizableLayout } from '@/components/resizable-layout'
import { ThemeToggle } from '@/components/theme-toggle'
import { UserIndicator } from '@/components/UserIndicator'
import { Button } from '@/components/ui/button'
import { PanelLeftOpen, PanelLeftClose, FileText, MessageSquare, Zap } from 'lucide-react'

type ViewMode = 'chat' | 'markdown' | 'split'

interface ProjectPageClientProps {
  slug: string
}

export default function ProjectPageClient({ slug }: ProjectPageClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('split') // Default to split view
  const [lastChatUpdate, setLastChatUpdate] = useState<number>(0)

  // Callback to notify when chat has new messages (for document refresh)
  const handleChatUpdate = useCallback(() => {
    setLastChatUpdate(Date.now())
  }, [])

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="h-16 border-b border-border bg-card flex items-center justify-between px-4 flex-shrink-0">
        <div className="flex items-center space-x-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="h-9 w-9 p-0"
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </Button>
          <h1 className="text-lg font-semibold text-foreground">
            {slug.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </h1>
          <div className="flex items-center text-xs text-primary bg-primary/10 px-2 py-1 rounded">
            <Zap className="h-3 w-3 mr-1" />
            AI-Enhanced
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {/* View Mode Toggle */}
          <div className="flex items-center space-x-1">
            <Button
              variant={viewMode === 'chat' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('chat')}
            >
              <MessageSquare className="h-4 w-4 mr-2" />
              Chat
            </Button>
            <Button
              variant={viewMode === 'split' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('split')}
            >
              Split
            </Button>
            <Button
              variant={viewMode === 'markdown' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('markdown')}
            >
              <FileText className="h-4 w-4 mr-2" />
              Document
            </Button>
          </div>

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* User Indicator */}
          <UserIndicator />
        </div>
      </header>

      {/* Main Content with Resizable Layout */}
      <div className="flex-1 overflow-hidden">
        <ResizableLayout
          sidebar={<ProjectSidebar currentSlug={slug} />}
          chat={<ChatWindow projectSlug={slug} onMessageComplete={handleChatUpdate} />}
          document={<MarkdownViewer projectSlug={slug} lastChatUpdate={lastChatUpdate} />}
          viewMode={viewMode}
          sidebarOpen={sidebarOpen}
        />
      </div>
    </div>
  )
}