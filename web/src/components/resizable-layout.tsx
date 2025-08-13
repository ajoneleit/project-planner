'use client'

import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels'
import { GripVertical } from 'lucide-react'

interface ResizableLayoutProps {
  sidebar: React.ReactNode
  chat: React.ReactNode
  document: React.ReactNode
  viewMode: 'chat' | 'markdown' | 'split'
  sidebarOpen: boolean
}

export function ResizableLayout({ 
  sidebar, 
  chat, 
  document, 
  viewMode, 
  sidebarOpen 
}: ResizableLayoutProps) {
  return (
    <div className="h-full flex bg-background">
      <PanelGroup direction="horizontal">
        {/* Sidebar Panel */}
        {sidebarOpen && (
          <>
            <Panel 
              defaultSize={20} 
              minSize={15} 
              maxSize={35}
              className="bg-card border-r border-border"
            >
              {sidebar}
            </Panel>
            <PanelResizeHandle className="w-1 bg-border hover:bg-primary/50 transition-colors duration-200 flex items-center justify-center group resize-handle">
              <GripVertical className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </PanelResizeHandle>
          </>
        )}

        {/* Main Content Panel */}
        <Panel className="flex flex-col">
          {viewMode === 'split' ? (
            <PanelGroup direction="horizontal">
              {/* Chat Panel */}
              <Panel 
                defaultSize={50} 
                minSize={30} 
                maxSize={70}
                className="border-r border-border flex flex-col"
              >
                {chat}
              </Panel>
              
              <PanelResizeHandle className="w-1 bg-border hover:bg-primary/50 transition-colors duration-200 flex items-center justify-center group resize-handle">
                <GripVertical className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
              </PanelResizeHandle>
              
              {/* Document Panel */}
              <Panel className="flex flex-col">
                {document}
              </Panel>
            </PanelGroup>
          ) : viewMode === 'chat' ? (
            <div className="flex-1 flex flex-col">
              {chat}
            </div>
          ) : (
            <div className="flex-1 flex flex-col">
              {document}
            </div>
          )}
        </Panel>
      </PanelGroup>
    </div>
  )
}