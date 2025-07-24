'use client'

import { useState } from 'react'
import { ProjectSidebar } from '@/components/project-sidebar'
import { ChatWindow } from '@/components/chat-window'
import { MarkdownViewer } from '@/components/markdown-viewer'
import { Button } from '@/components/ui/button'
import { PanelLeftOpen, PanelLeftClose, FileText, MessageSquare } from 'lucide-react'

type ViewMode = 'chat' | 'markdown' | 'split'

interface ProjectPageClientProps {
  slug: string
}

export default function ProjectPageClient({ slug }: ProjectPageClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('chat')

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className={`transition-all duration-300 ${sidebarOpen ? 'w-80' : 'w-0'} overflow-hidden border-r bg-white`}>
        <ProjectSidebar currentSlug={slug} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 border-b bg-white flex items-center justify-between px-4">
          <div className="flex items-center space-x-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
            </Button>
            <h1 className="text-lg font-semibold">
              {slug.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </h1>
          </div>

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
              variant={viewMode === 'markdown' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('markdown')}
            >
              <FileText className="h-4 w-4 mr-2" />
              Document
            </Button>
            <Button
              variant={viewMode === 'split' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('split')}
            >
              Split
            </Button>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 flex overflow-hidden">
          {/* Chat Window */}
          {(viewMode === 'chat' || viewMode === 'split') && (
            <div className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} border-r`}>
              <ChatWindow projectSlug={slug} />
            </div>
          )}

          {/* Markdown Viewer */}
          {(viewMode === 'markdown' || viewMode === 'split') && (
            <div className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'}`}>
              <MarkdownViewer projectSlug={slug} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}