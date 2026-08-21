import type { Metadata } from "next";
import "./globals.css";


export const metadata: Metadata = {
  title: "PDF Scraper — ACROSET Conference Tools",
  description: "Scrape, compile, and generate conference paper compilations from PDF documents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Amatic+SC&family=Bangers&family=Bebas+Neue&family=Black+Ops+One&family=Caveat&family=Cinzel&family=Creepster&family=Dancing+Script&family=Lobster&family=Montserrat&family=Orbitron&family=Oswald&family=Pacifico&family=Permanent+Marker&family=Righteous&family=Russo+One&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="dashboard-layout">
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
