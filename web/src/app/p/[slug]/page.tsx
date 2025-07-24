import ProjectPageClient from './project-page-client'

// This function is required for static export with dynamic routes
export async function generateStaticParams() {
  // Return empty array for now - pages will be generated on demand
  return []
}

interface ProjectPageProps {
  params: Promise<{ slug: string }>
}

export default async function ProjectPage({ params }: ProjectPageProps) {
  const { slug } = await params
  return <ProjectPageClient slug={slug} />
}