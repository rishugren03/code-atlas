import "./globals.css";

export const metadata = {
  title: "CodeAtlas — Open Source Evolution Explorer",
  description:
    "Visualize the full evolution, relationships, and influence of software projects across the open-source ecosystem. Explore commit timelines, contributor networks, and dependency graphs.",
  keywords: [
    "open source",
    "code evolution",
    "git history",
    "dependency graph",
    "contributor network",
    "code visualization",
  ],
  openGraph: {
    title: "CodeAtlas — Open Source Evolution Explorer",
    description:
      "The Google Maps for Software History. Explore how open-source projects evolved.",
    type: "website",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
