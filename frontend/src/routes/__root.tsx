import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";

import appCss from "../style.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { Toaster } from "@/components/ui/sonner";
import { HistorySidebar } from "@/components/HistorySidebar";
import { ThemeProvider, useTheme } from "@/lib/theme";
import { LiquidButton } from "@/components/ui/button";
import { Bot, Sun, Moon } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";

import "@fontsource/albert-sans/400.css";
import "@fontsource/albert-sans/500.css";
import "@fontsource/albert-sans/600.css";
import "@fontsource/albert-sans/700.css";


function ThemeTextToggle() {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";
  return (
    <button 
      onClick={toggle}
      className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface/30 backdrop-blur-md border border-line/30 shadow-sm hover:bg-surface/50 transition-all duration-300 text-xs font-medium text-foreground group"
    >
      <div className="relative flex h-4 w-4 items-center justify-center">
        <Sun className={`absolute h-4 w-4 transition-all duration-500 ${isDark ? 'rotate-90 opacity-0 scale-0' : 'rotate-0 opacity-100 scale-100'}`} />
        <Moon className={`absolute h-4 w-4 transition-all duration-500 ${isDark ? 'rotate-0 opacity-100 scale-100' : '-rotate-90 opacity-0 scale-0'}`} />
      </div>
      <span className="opacity-80 group-hover:opacity-100 transition-opacity">
        {isDark ? "Light" : "Dark"}
      </span>
    </button>
  );
}

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Agentic SDLC Orchestrator" },
      { name: "description", content: "Turn a one-line brief into a full software delivery lifecycle — requirements, design, sprint plan, code, and tests — run by autonomous AI agents." },
      { name: "author", content: "Lovable" },
      { property: "og:title", content: "Agentic SDLC Orchestrator" },
      { property: "og:description", content: "Turn a one-line brief into a full software delivery lifecycle — requirements, design, sprint plan, code, and tests — run by autonomous AI agents." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:site", content: "@Lovable" },
      { name: "twitter:title", content: "Agentic SDLC Orchestrator" },
      { name: "twitter:description", content: "Turn a one-line brief into a full software delivery lifecycle — requirements, design, sprint plan, code, and tests — run by autonomous AI agents." },
      { property: "og:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/72961413-08e7-4385-a155-4a10790c3a12/id-preview-0865522b--347d6dcc-90c1-4866-a74c-52c7c7e5eced.lovable.app-1783949527513.png" },
      { name: "twitter:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/72961413-08e7-4385-a155-4a10790c3a12/id-preview-0865522b--347d6dcc-90c1-4866-a74c-52c7c7e5eced.lovable.app-1783949527513.png" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body className="font-sans antialiased">
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <ThemeProvider>
      <TooltipProvider>
        <QueryClientProvider client={queryClient}>
        <div className="flex h-screen w-full bg-background">
          <div 
            className={`hidden md:flex flex-col py-4 overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] ${
              isSidebarOpen ? "w-80 pl-4 opacity-100" : "w-0 pl-0 opacity-0"
            }`}
          >
            <div className="w-72 h-full flex flex-col bg-sidebar border border-sidebar-border rounded-2xl shadow-xl overflow-hidden">
              <HistorySidebar onClose={() => setIsSidebarOpen(false)} />
            </div>
          </div>
          
          <main className="flex-1 w-full h-full relative overflow-y-auto transition-all duration-300">
            
            <div className={`absolute top-10 left-8 z-50 flex items-center gap-3 ${isSidebarOpen ? "hidden" : "flex"}`}>
              <LiquidButton
                onClick={() => setIsSidebarOpen(true)}
                size="icon"
                className="h-12 w-12 shrink-0 rounded-full shadow-lg"
                title="Open Sidebar"
              >
                <Bot className="h-6 w-6" />
              </LiquidButton>
            </div>
            
            <div className="absolute bottom-8 right-8 z-50">
              <ThemeTextToggle />
            </div>
            {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
            <Outlet />
          </main>
        </div>
        <Toaster position="top-center" />
      </QueryClientProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
