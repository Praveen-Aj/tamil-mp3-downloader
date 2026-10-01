# V6 VISUAL DESIGN SPECIFICATION

## 1. Executive Visual Diagnosis
The current UI is highly functional but visually suffers from "AI Engineering Dashboard Syndrome". The dominance of navy blue backgrounds (`#080c14`), dual-accent neon gradients (indigo + cyan), and table-heavy layouts make it feel like a database admin tool or monitoring console rather than a premium consumer music application. The goal of this redesign is to implement a strict "content-first" graphite and charcoal theme, reducing interface noise so that the album artwork provides the primary color and warmth.

## 2. Screenshot-based Evidence
Based on the current rendered state captured in `docs/ui-ux/v6-redesign-validation-current`:
- **desktop-01-dashboard.png**: Showcases the heavy use of dark blue (`#080c14`) and indigo accents. Cards have pronounced glowing borders on hover that distract from the artwork.
- **desktop-11-sidebar-nav.png**: The logo uses a heavy cyan-to-indigo gradient (`#6366f1` to `#06b6d4`). Active navigation items use a loud translucent blue background block.
- **desktop-02-songs.png**: The list views rely on dense data tables with brightly colored status badges that compete with primary actions.
- **mobile-02-player-nav.png**: Mobile layout creates visual clutter at the bottom of the screen with a "double decker" persistent player and bottom navigation bar competing for space and attention.

## 3. Problems Ranked by Visual Impact
1. **Background & Surface Tones**: Navy/blue tints make the app feel cold and developer-centric.
2. **Dual-Accent Gradients**: The indigo (`#6366f1`) and cyan (`#06b6d4`) pairing is a generic AI default that feels unrefined.
3. **Overuse of Glow and Heavy Borders**: "Glass" panels and buttons rely on glowing box-shadows rather than subtle surface hierarchy.
4. **Pill Badge Clutter**: Semantic role badges and quality tags are too saturated and draw the eye away from content (artwork and titles).
5. **Sidebar Active States**: The active state in the sidebar is too heavy, creating a blocky appearance.

## 4. Final Visual Direction
- **Foundation**: True graphite and charcoal (no blue tint). `#0B0B0D` base.
- **Surfaces**: Subtle, neutral surface layers (`#1A1A1F`) relying on 1px inner borders for definition rather than heavy drop shadows or glow.
- **Accent**: ONE restrained primary accent color (a soft violet/indigo: `#8B7CF8`) used sparingly for primary actions and active indicators.
- **Color Source**: The interface should remain monochromatic and neutral; all vibrancy should come from the album artwork and artist images.
- **Typography**: Switch to a geometric sans-serif (e.g., Plus Jakarta Sans) or utilize Outfit universally for a slightly more premium, rounded consumer feel.

## 5. Design Tokens
The following token system must be strictly applied via `tokens.css`:

```css
:root {
  /* BACKGROUNDS (Graphite/Charcoal) */
  --bg-app: #0B0B0D;
  --bg-sidebar: #0F0F12;
  --bg-header: #0F0F12;
  --bg-player: rgba(11, 11, 13, 0.97);
  --bg-surface: #1A1A1F;
  --bg-surface-hover: #202028;
  --bg-surface-active: #26262F;
  --bg-inset: #080809;
  --bg-glass: rgba(26, 26, 31, 0.88);
  
  /* ACCENT (Single Restrained Violet) */
  --accent-primary: #8B7CF8;
  --accent-primary-hover: #7A6BE8;
  --accent-primary-glow: rgba(139, 124, 248, 0.10);
  
  /* TEXT (Neutral, no blue cast) */
  --text-primary: #F4F4F6;
  --text-secondary: #8A8A96;
  --text-muted: #56565E;
  --text-inverse: #0B0B0D;
  
  /* BORDERS */
  --border-subtle: rgba(255, 255, 255, 0.04);
  --border-medium: rgba(255, 255, 255, 0.08);
  --border-focus: #8B7CF8;
  
  /* SEMANTIC STATUS (For Badges/Toasts ONLY) */
  --color-success: #22C55E;
  --color-warning: #F59E0B;
  --color-error: #F87171;
  --color-info: #8B7CF8; /* Mapped to primary accent */
}
```
*Note: Semantic colors exist separately because they communicate standard states (success, warning, error) that cannot be expressed with the primary brand violet.*

## 6. Typography
- **Primary Body**: `Plus Jakarta Sans` or fallback to `Inter` (adjusted for tabular numbers).
- **Display/Headings**: `Outfit` for a friendly, modern music identity.
- **Hierarchy**: Rely on font weight and text color (`--text-secondary` vs `--text-primary`) rather than size alone to establish hierarchy.

## 7. Navigation
- **Desktop Sidebar**:
  - Logo: Replace the neon gradient background with a flat or highly subtle violet background.
  - Active State: Remove the translucent background block. Use a `var(--text-primary)` font color, a subtle left-border (`3px solid var(--accent-primary)`), and a very faint gradient or text-shadow if necessary.
- **Mobile Bottom Nav**:
  - Keep 4-5 core destinations.
  - Active State: Simple accent tint on the icon. No pills.

## 8. Page-by-Page Specifications
- **Dashboard**: Remove neon glows from "Featured" cards. Ensure album art sits flush or with a subtle 1px inner ring.
- **Songs**: Reduce table border visibility. Remove opaque background fills from quality badges (use subtle text coloring or muted pill backgrounds). 
- **Movies**: Poster grid should prioritize the artwork. The "Play" button overlay should use the restrained violet, not the neon indigo.
- **Artists / Artist Detail**: Avatars remain circular. Remove heavy blue box-shadows on hover. Role semantic badges (Composer vs Singer) should use muted semantic backgrounds (e.g., emerald for singer, violet for composer).
- **Search**: The dropdown should feel like a native Spotlight search (graphite surface, subtle borders) rather than a heavy modal.
- **Downloads**: Present as a consumer queue. Use a thin line for progress bars instead of thick, striped blocks. Hide raw file paths unless hovered or expanded.
- **Charts / Empty States**: Use muted wireframe SVGs or simple typography with a soft `--text-muted` color. No loud error/info boxes for an empty list.
- **Settings & Import**: Visually group developer/system configurations separately from user preferences. Use subtle dividing lines.

## 9. Component Rules
- **Buttons**: Primary buttons use flat `--accent-primary`. No intense box-shadows. Ghost/Icon buttons should have transparent backgrounds and only show a subtle `--bg-surface-hover` on hover.
- **Badges**: Convert from high-saturation fills to `rgba(255,255,255,0.06)` backgrounds with colored text, or use the muted `--color-success-bg` variables.
- **Cards**: No outer glow on hover. Rely on background color shifting (e.g., `--bg-surface` to `--bg-surface-hover`) and a slight upward transform.
- **Tables**: Borderless rows, subtle `--border-subtle` dividers. Selected rows get a very faint `--accent-primary-glow` background.
- **Player**: The persistent bottom player is currently well-structured. Adjust its background to `--bg-player` (graphite glass) and ensure the progress bar uses the single violet accent.

## 10. Mobile Rules (390px)
- **Player Integration**: The player must cleanly stack above the bottom navigation without fighting for hierarchy. Consider a unified glass panel that houses both, or a mini-player that collapses neatly.
- **Lists**: Tables must convert to flex-row list items on mobile.
- **Hit Targets**: All interactive elements (play buttons, nav icons) must be at least 44x44px.
- **Content Space**: Hide secondary metadata (like bitrates or exact file sizes) in list views to prioritize Song Title and Artist.

## 11. Accessibility Rules
- Maintain contrast ratios of at least 4.5:1 for all text against `--bg-app` and `--bg-surface`.
- Focus states must use `--border-focus` (solid violet) rather than relying solely on background shifts.
- Ensure all icon-only buttons (like play/pause/skip) retain proper `aria-label` tags.

## 12. Download UI Rules
- Do not show raw filesystem paths (`C:\Users\...`) prominently in the main UI list; reserve this for tooltips or a "Details" view.
- Show clear human-readable states: "Queued", "Downloading", "Completed", "Failed".
- A failed download should show a subtle retry icon, not a massive red error block.

## 13. Download-Path Persistence Findings
**CRITICAL AUDIT DISCOVERY**:
- The download path is configured and persisted in `config/settings.json` under `"download": { "output_dir": "C:\\Users\\Praveen\\Downloads\\Songs New", ... }`.
- `config/settings.py` loads this JSON file into memory on startup and writes back to it via the `save()` method.
- The `output_dir` property resolves this path authoritatively.
- Database locations are stored in the OS-specific user data dir (`%APPDATA%\tamil-mp3-downloader\library.db`).
- **Conclusion**: Restarting the application preserves the configured download path perfectly because it is written to the physical JSON file. **These paths must NOT be altered during implementation.**

## 14. Preservation Constraints
The final implementation MUST preserve:
- FastAPI backend and all REST/WebSocket routes.
- The canonical SQLite database and existing library files.
- Download logic, discovery providers, and filesystem deduplication.
- The absolute download path: `C:\Users\Praveen\Downloads\Songs New`.
- Existing navigation labels and core routing structure.

## 15. Implementation Order
1. **Tokens**: Overwrite `web/src/styles/tokens.css` with the new graphite/violet variables.
2. **Main CSS**: Update hardcoded overrides in `web/src/styles/main.css`.
3. **Typography**: Update `index.html` to load Plus Jakarta Sans.
4. **Layout Components**: Update `Sidebar.tsx` and `PlayerBar.tsx` hardcoded colors.
5. **View Components**: Systematically remove hardcoded `rgba(99, 102, 241, X)` values across `SongsView.tsx`, `MoviesView.tsx`, `ArtistsView.tsx`, etc.
6. **Mobile Polish**: Verify responsive behavior of the player + bottom nav.

## 16. Acceptance Criteria
- Visually, the app appears charcoal/graphite with a single violet accent.
- Cyan is completely removed from the UI.
- No functionality, API calls, or backend logic is modified.
- Screenshots taken post-implementation match the aesthetic specifications defined in this document.
- The authoritative download path remains completely untouched and functional.
