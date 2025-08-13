'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Textarea } from '@/components/ui/textarea'
import { Plus, Folder, Calendar, Loader2, Archive, MoreVertical, Trash2, ArchiveRestore } from 'lucide-react'
import { cn } from '@/lib/utils'
import { apiRequest, archiveProject, unarchiveProject, deleteProject, fetchArchivedProjects } from '@/lib/api'

interface Project {
  slug: string
  name: string
  created: string
  status: string
}

interface CreateProjectData {
  name: string
  description: string
}

async function fetchProjects(): Promise<Project[]> {
  return apiRequest<Project[]>('/api/projects')
}

async function createProject(data: CreateProjectData): Promise<{ slug: string; message: string }> {
  return apiRequest<{ slug: string; message: string }>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

interface ProjectSidebarProps {
  currentSlug: string
}

export function ProjectSidebar({ currentSlug }: ProjectSidebarProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDescription, setNewProjectDescription] = useState('')
  const [activeTab, setActiveTab] = useState('active')

  const { data: projects, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const { data: archivedProjects, isLoading: archivedLoading } = useQuery({
    queryKey: ['projects', 'archived'],
    queryFn: fetchArchivedProjects,
    refetchInterval: 30000,
  })

  const createProjectMutation = useMutation({
    mutationFn: createProject,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setCreateDialogOpen(false)
      setNewProjectName('')
      setNewProjectDescription('')
      router.push(`/p/${data.slug}`)
    },
    onError: (error) => {
      console.error('Failed to create project:', error)
    }
  })

  const archiveMutation = useMutation({
    mutationFn: archiveProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['projects', 'archived'] })
    },
    onError: (error) => {
      console.error('Failed to archive project:', error)
    }
  })

  const unarchiveMutation = useMutation({
    mutationFn: unarchiveProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['projects', 'archived'] })
    },
    onError: (error) => {
      console.error('Failed to unarchive project:', error)
    }
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['projects', 'archived'] })
    },
    onError: (error) => {
      console.error('Failed to delete project:', error)
    }
  })

  const handleCreateProject = () => {
    if (newProjectName.trim()) {
      createProjectMutation.mutate({
        name: newProjectName.trim(),
        description: newProjectDescription.trim(),
      })
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString()
    } catch {
      return 'Unknown'
    }
  }

  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-4 bg-card">
        <div className="text-center">
          <p className="text-destructive font-medium mb-2">Failed to load projects</p>
          <p className="text-sm text-muted-foreground">Check your connection and try again</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-card">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-card-foreground">Projects</h2>
          
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-2" />
                New
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Project</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-foreground">Project Name</label>
                  <Input
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="Enter project name..."
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Description (Optional)</label>
                  <Textarea
                    value={newProjectDescription}
                    onChange={(e) => setNewProjectDescription(e.target.value)}
                    placeholder="Describe your project..."
                    className="mt-1"
                    rows={3}
                  />
                </div>
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button 
                    onClick={handleCreateProject}
                    disabled={!newProjectName.trim() || createProjectMutation.isPending}
                  >
                    {createProjectMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    )}
                    Create Project
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        
        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="active" className="flex-1">
              <Folder className="h-4 w-4 mr-2" />
              Active
            </TabsTrigger>
            <TabsTrigger value="archived" className="flex-1">
              <Archive className="h-4 w-4 mr-2" />
              Archived
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Projects List */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsContent value="active">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : !projects || projects.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Folder className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-sm">No active projects</p>
                  <p className="text-xs">Create your first project to get started</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {projects.map((project) => (
                    <div key={project.slug} className="group relative">
                      <button
                        onClick={() => router.push(`/p/${project.slug}`)}
                        className={cn(
                          "w-full text-left p-3 rounded-lg transition-colors pr-10",
                          "hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring",
                          currentSlug === project.slug ? "bg-accent border border-border" : "border border-transparent"
                        )}
                      >
                        <div className="flex items-start space-x-3">
                          <Folder className={cn(
                            "h-5 w-5 mt-0.5 flex-shrink-0",
                            currentSlug === project.slug ? "text-primary" : "text-muted-foreground"
                          )} />
                          <div className="flex-1 min-w-0">
                            <p className={cn(
                              "font-medium text-sm truncate",
                              currentSlug === project.slug ? "text-foreground" : "text-foreground"
                            )}>
                              {project.name}
                            </p>
                            <div className="flex items-center mt-1">
                              <Calendar className="h-3 w-3 text-muted-foreground mr-1" />
                              <p className="text-xs text-muted-foreground">
                                {formatDate(project.created)}
                              </p>
                            </div>
                          </div>
                        </div>
                      </button>
                      
                      {/* Actions dropdown */}
                      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => archiveMutation.mutate(project.slug)}
                              disabled={archiveMutation.isPending}
                            >
                              <Archive className="h-4 w-4 mr-2" />
                              Archive
                            </DropdownMenuItem>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                                  <Trash2 className="h-4 w-4 mr-2 text-red-500" />
                                  <span className="text-red-500">Delete</span>
                                </DropdownMenuItem>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Delete Project</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Are you sure you want to delete &ldquo;{project.name}&rdquo;? This action cannot be undone and all project data will be permanently lost.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction
                                    onClick={() => deleteMutation.mutate(project.slug)}
                                    className="bg-red-600 hover:bg-red-700"
                                    disabled={deleteMutation.isPending}
                                  >
                                    {deleteMutation.isPending && (
                                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    )}
                                    Delete
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
            
            <TabsContent value="archived">
              {archivedLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : !archivedProjects || archivedProjects.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Archive className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-sm">No archived projects</p>
                  <p className="text-xs">Archived projects will appear here</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {archivedProjects.map((project) => (
                    <div key={project.slug} className="group relative">
                      <button
                        onClick={() => router.push(`/p/${project.slug}`)}
                        className="w-full text-left p-3 rounded-lg transition-colors pr-10 hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring border border-transparent"
                      >
                        <div className="flex items-start space-x-3">
                          <Archive className="h-5 w-5 mt-0.5 flex-shrink-0 text-muted-foreground" />
                          <div className="flex-1 min-w-0 opacity-75">
                            <p className="font-medium text-sm truncate text-foreground">
                              {project.name}
                            </p>
                            <div className="flex items-center mt-1">
                              <Calendar className="h-3 w-3 text-muted-foreground mr-1" />
                              <p className="text-xs text-muted-foreground">
                                {formatDate(project.created)}
                              </p>
                            </div>
                          </div>
                        </div>
                      </button>
                      
                      {/* Actions dropdown */}
                      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => unarchiveMutation.mutate(project.slug)}
                              disabled={unarchiveMutation.isPending}
                            >
                              <ArchiveRestore className="h-4 w-4 mr-2" />
                              Unarchive
                            </DropdownMenuItem>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                                  <Trash2 className="h-4 w-4 mr-2 text-red-500" />
                                  <span className="text-red-500">Delete</span>
                                </DropdownMenuItem>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Delete Project</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Are you sure you want to delete &ldquo;{project.name}&rdquo;? This action cannot be undone and all project data will be permanently lost.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction
                                    onClick={() => deleteMutation.mutate(project.slug)}
                                    className="bg-red-600 hover:bg-red-700"
                                    disabled={deleteMutation.isPending}
                                  >
                                    {deleteMutation.isPending && (
                                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    )}
                                    Delete
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </ScrollArea>
    </div>
  )
}