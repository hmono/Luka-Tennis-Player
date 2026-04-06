type MainLayoutProps = {
  title: string;
  description: string;
  children?: React.ReactNode;
};

export default function MainLayout({
  title,
  description,
  children,
}: MainLayoutProps) {
  return (
    <section className="shell section-block">
      <div className="hero-panel">
        <p className="mb-4 text-xs font-medium uppercase tracking-[0.24em] text-white/60">
          MainLayout
        </p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">
          {title}
        </h1>
        <p className="mt-6 max-w-2xl text-sm leading-7 text-white/75 sm:text-base">
          {description}
        </p>
      </div>

      {children ? (
        <div className="mt-8">{children}</div>
      ) : (
        <div className="surface-card mt-8 p-6">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-black/45">
            Placeholder
          </p>
          <p className="mt-3 text-lg font-semibold">Page implementation pending</p>
        </div>
      )}
    </section>
  );
}
