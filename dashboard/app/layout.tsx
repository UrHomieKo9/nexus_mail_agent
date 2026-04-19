import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "./components/Sidebar";
import { UserProvider } from "./providers";

export const metadata: Metadata = {
  title: "Nexus Mail Agent — Dashboard",
  description:
    "AI-powered outreach automation and email management platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <UserProvider>
          <div className="app-shell">
            <Sidebar />
            <main className="main-content">{children}</main>
          </div>
        </UserProvider>
      </body>
    </html>
  );
}
