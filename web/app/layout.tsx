export const metadata = {
  title: "FO Intel — Family Office Search",
  description: "Query verified family office intelligence. Answers stay within sourced records.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "Georgia, 'Times New Roman', serif", background: "#f4f1ea", color: "#1a1a1a" }}>
        {children}
      </body>
    </html>
  );
}
