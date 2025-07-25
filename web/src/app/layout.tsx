import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ReactQueryProvider } from '@/components/providers/react-query-provider'
import { UserProvider } from '@/contexts/UserContext'
import { AutoUserIdentityModal } from '@/components/UserIdentityModal'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Project Planner Bot',
  description: 'AI-powered project planning with markdown memory',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ReactQueryProvider>
          <UserProvider>
            {children}
            <AutoUserIdentityModal />
          </UserProvider>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
