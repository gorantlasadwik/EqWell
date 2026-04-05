# Design System Strategy: The Mindful Curator

## 1. Overview & Creative North Star
This design system moves away from the rigid, modular grid systems typical of utility apps and instead embraces the philosophy of **"The Mindful Curator."** The goal is to create a digital sanctuary for students that feels editorial, bespoke, and intentionally paced. 

Rather than overwhelming the user with dense data tables and sharp boundaries, we use **Organic Brutalism**: a combination of hyper-rounded corners (32px+), asymmetrical layouts, and soft tonal layering. This approach breaks the "template" look by treating the interface as a series of curated physical layers—like high-end stationery or frosted glass—resting on a warm, breathable surface. It prioritizes the student’s mental state by reducing visual noise and using "energy-mapped" colors to guide focus.

---

## 2. Colors: Tonal Depth over Structural Lines
Our palette is rooted in a warm, tactile foundation. It is designed to feel human, not clinical.

### The Palette
*   **Surface Foundation:** The `background` (`#fcf9f4`) is a soft cream that reduces eye strain compared to pure white.
*   **The Power of Dark Charcoal:** The `primary` (`#060607`) is reserved for high-impact typography and primary CTAs to provide a sophisticated, authoritative anchor.
*   **Vibrant Accents (Energy & Signal):** 
    *   **Secondary (Yellow):** Use `secondary_container` (`#fdc003`) for energy, focus, and positive habits.
    *   **Tertiary (Coral/Red):** Use `on_tertiary_container` (`#da624d`) sparingly to denote stress signals or areas requiring immediate empathy.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to define sections. Boundaries must be created through:
1.  **Background Shifts:** Place a `surface_container_low` card on a `surface` background.
2.  **Tonal Transitions:** Use subtle shifts between `surface_container` tiers to denote hierarchy.

### The "Glass & Gradient" Rule
To achieve a premium, custom feel:
*   **Floating Elements:** Use `surface_container_lowest` with a 70% opacity and a `backdrop-blur` (20px-40px) for navigation bars or floating action buttons.
*   **Signature Textures:** For hero sections or data visualizations, use soft radial gradients transitioning from `primary` to `primary_container`. This adds a "soulful" depth that flat color cannot replicate.

---

## 3. Typography: The Editorial Voice
We utilize a high-contrast typography scale to create an editorial rhythm.

*   **Display & Headlines:** Using **Plus Jakarta Sans**. These should be used with generous leading. The `display-lg` (3.5rem) should be used for personal greetings and "Big Wins" to make the app feel conversational.
*   **Body & UI Labels:** Using **Inter**. This provides a clean, neutral balance to the expressive headlines. `body-lg` (1rem) is the standard for empathetic content, while `label-md` (0.75rem) handles the utilitarian metadata.
*   **Hierarchy Tip:** Pair a `display-sm` headline with a `label-md` (all caps, 0.05em letter spacing) directly above it to create a sophisticated, magazine-style header.

---

## 4. Elevation & Depth: Tonal Layering
Traditional shadows are secondary to **Tonal Layering**. We convey importance by "stacking" surfaces.

*   **The Layering Principle:** 
    *   **Level 0:** `surface` (The floor)
    *   **Level 1:** `surface_container_low` (Large background sections)
    *   **Level 2:** `surface_container_highest` (Interactive cards/Active states)
*   **Ambient Shadows:** When a "floating" effect is required, shadows must be extra-diffused. 
    *   *Shadow Token:* `color: rgba(28, 28, 25, 0.06); blur: 48px; spread: 0; y: 12px;`
*   **The "Ghost Border":** If a container sits on a background of the same color, use a 1px border with the `outline_variant` token at **15% opacity**. Never use a 100% opaque border.

---

## 5. Components: Soft & Intentional

### Buttons
*   **Primary:** High-pill shape (`rounded-full`), `primary` background, `on_primary` text.
*   **Secondary:** `surface_container_highest` background with `on_surface` text.
*   **Interaction:** On hover, a subtle scale-up (1.02x) is preferred over a color change.

### Cards (The Core Pattern)
*   **Standard Card:** Radius `lg` (2rem/32px) or `xl` (3rem/48px). No borders.
*   **Data Cards:** Use the "Editorial Data" style seen in the reference—blurred, organic blobs for mood visualizations instead of sharp line graphs. Use `secondary` (yellow) and `on_tertiary_container` (coral) for these blurred elements.

### Inputs & Fields
*   **Text Inputs:** Use `surface_container_low` for the field background. The corner radius should match the `md` scale (1.5rem).
*   **Forbid Dividers:** In lists or settings, never use a line to separate items. Use vertical white space (from the spacing scale) or a 4px gap between distinct `surface_container` blocks.

### Additional Signature Component: The "Reflection Blob"
A decorative, slowly animating background element using a blurred `secondary_fixed` gradient. This provides a calming, living feel to the "Mindful Curator" experience.

---

## 6. Do’s and Don’ts

### Do
*   **Do** embrace negative space. If a screen feels full, increase the padding.
*   **Do** use asymmetrical card widths (e.g., a 60% width card next to a 40% width card) to break the "standard app" feel.
*   **Do** use the `xl` (3rem) corner radius for main dashboard containers to emphasize a soft, friendly touch.

### Don't
*   **Don't** use standard Material Design elevation (heavy drop shadows).
*   **Don't** use high-contrast dividers or 100% black text on pure white backgrounds.
*   **Don't** crowd the interface. If a piece of information isn't vital to the student's wellbeing in the moment, hide it behind a "More" action.
*   **Don't** use sharp corners (0-12px) anywhere. They trigger a "clinical" or "unfriendly" subconscious response.