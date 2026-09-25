# PokeDex TeamTypeMatchup - Frontend

React + TypeScript frontend client built with Vite and TailwindCSS.

## Requirements
- Node.js 18+ (Node.js v22 tested)
- npm 9+ (npm v10 tested)

## Setup & Local Execution

1. **Install Dependencies:**
   ```cmd
   npm install
   ```

2. **Environment Configuration:**
   - Copy `.env.example` to `.env`:
     ```cmd
     copy .env.example .env
     ```
   - Default connects to backend at `http://localhost:8000/api/v1`.

3. **Start Development Server:**
   ```cmd
   npm run dev
   ```
   - The Vite development server runs at `http://localhost:3000`.
   - API calls to `/api` are automatically proxied to the backend at `http://127.0.0.1:8000`.

4. **Build & Type Check:**
   ```cmd
   npm run build
   ```
