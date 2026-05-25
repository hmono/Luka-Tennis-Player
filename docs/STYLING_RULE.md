# Styling Rule

One system: **CSS component classes** defined in `src/styles/components.css`.  
Tailwind v4 is the build layer; its utilities are available but component classes are preferred.

## Inline styles: permitted / forbidden

| Case | Rule | Example |
|------|------|---------|
| Dynamic value from JS | ✅ Permitted | `style={{ width: \`${pct}%\` }}` |
| Dynamic color from JS | ✅ Permitted | `style={{ background: accentColor }}` |
| Static value any kind | ❌ Forbidden | `style={{ marginBottom: "20px" }}` |
| Hardcoded colour literal | ❌ Forbidden | `style={{ color: "rgba(0,0,0,0.45)" }}` |
| Hardcoded font family | ❌ Forbidden | `style={{ fontFamily: "'IBM Plex Mono', monospace" }}` |

If a static value is missing from `components.css`, add it there — never inline it.

## Token usage

All colours, fonts, and spacing scale live in `src/styles/tokens.css` as CSS custom properties.
Reference them via `var(--luka-blue)`, `var(--font-mono)`, etc.  
Never hardcode a hex value or font string in a component file.
