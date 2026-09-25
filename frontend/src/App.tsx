import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Shield, Sparkles } from 'lucide-react'

const queryClient = new QueryClient()

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6">
        <header className="max-w-2xl w-full text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-800 border border-slate-700 text-sky-400 font-medium text-sm">
            <Shield className="w-4 h-4" />
            <span>PokeDex TeamTypeMatchup - Milestone 0 Ready</span>
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
            PokeDex TeamTypeMatchup
          </h1>
          <p className="text-slate-400 text-base sm:text-lg">
            Game-aware team building and type matchup analysis. Scaffolding and environment initialized successfully.
          </p>
          <div className="p-4 rounded-lg bg-slate-900 border border-slate-800 text-sm text-slate-300 flex items-center justify-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>Frontend stack: React 18, TypeScript, TailwindCSS, TanStack Query, Lucide Icons.</span>
          </div>
        </header>
      </div>
    </QueryClientProvider>
  )
}

export default App
