import ProjectPageClient from './project-page-client'

// This function is required for static export with dynamic routes
export async function generateStaticParams() {
  // For static export, we'll generate a demo page
  // In practice, users will navigate to project pages dynamically
  return [
    { slug: 'demo' }
  ]
}

interface ProjectPageProps {
  params: Promise<{ slug: string }>
}

export default async function ProjectPage({ params }: ProjectPageProps) {
  const { slug } = await params
  return <ProjectPageClient slug={slug} />
}