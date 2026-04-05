# Design System Document: The Serene Intelligence

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Sanctuary"**

This design system moves away from the cold, clinical aesthetic typical of health tech, favoring instead a high-end, editorial approach to student wellbeing. We are building a "Digital Sanctuary"—an environment that feels as quiet and intentional as a high-end library or a modern meditation space. 

To break the "template" look, we employ **Intentional Asymmetry**. Instead of rigid, centered grids, we use generous, purposeful whitespace and offset layouts to guide the eye. Overlapping elements and varying container heights create a sense of organic movement, ensuring the data-driven AI aspects feel supportive and human rather than invasive or robotic.

---

## 2. Colors & Tonal Depth
Our palette is rooted in the intersection of nature and clarity. We utilize deep teals and soft forest greens to ground the user, while airy blues and cool neutrals provide breathing room.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning or containment. 
Structure is defined through **Background Color Shifts**. For instance, a section utilizing `surface-container-low` sits directly on a `surface` background. The transition between these tones is the boundary. This creates a seamless, "liquid" UI that feels professional and expensive.

### Surface Hierarchy & Nesting
Treat the interface as a physical stack of fine paper or frosted glass.
*   **Base:** `surface` (#f8f9ff)
*   **Subtle Recess:** `surface-container-low` (#eff4ff)
*   **Active Layers:** `surface-container` (#e5eeff)
*   **Emphasis Layers:** `surface-container-highest` (#d2e4ff)

### The "Glass & Gradient" Rule
To add soul to the AI experience, use subtle gradients for primary actions or hero states, transitioning from `primary` (#266774) to `primary-container` (#aceaf9). For floating modals or navigation bars, apply **Glassmorphism**: use a semi-transparent `surface` color with a `backdrop-filter: blur(20px)`. This allows the student’s personalized content to bleed through softly, reinforcing the "privacy-first" transparency.

---

## 3. Typography
We utilize a sophisticated dual-type system to balance authority with accessibility.

*   **Display & Headlines (Manrope):** This geometric sans-serif serves as our editorial voice. It feels modern and "data-driven" but retains a friendly roundness. Use `display-lg` for large, welcoming headers that feel like a magazine spread.
*   **Body & Labels (Inter):** Chosen for its exceptional legibility at small sizes. Inter handles the "privacy" and "data" heavy lifting. It ensures that even complex wellbeing insights are easy to digest.
*   **Hierarchy as Identity:** By using high-contrast scales (e.g., a `display-md` headline next to a `body-md` description), we create a sense of importance and clarity without needing bold colors or heavy lines.

---

## 4. Elevation & Depth
In this design system, depth is a feeling, not a shadow.

*   **Tonal Layering:** Achieve hierarchy by stacking. Place a `surface-container-lowest` (#ffffff) card on top of a `surface-container-low` (#eff4ff) section. This creates a natural "lift" that mimics ambient light hitting a surface.
*   **Ambient Shadows:** When a true float is required (e.g., a floating action button), use an ultra-diffused shadow: `box-shadow: 0 12px 40px rgba(5, 52, 92, 0.06)`. Note the use of `on-surface` (#05345c) as the shadow tint rather than pure black.
*   **The "Ghost Border" Fallback:** If a boundary is required for accessibility, use the `outline-variant` token (#91b4e4) at **15% opacity**. It should be felt, not seen.

---

## 5. Components

### Buttons
*   **Primary:** A gradient-filled container (`primary` to `primary-dim`) with `on-primary` text. `xl` (1.5rem) rounded corners are mandatory.
*   **Secondary:** No fill. Use `surface-container-high` as the background on hover.
*   **Tertiary:** Pure text using `primary` color with a subtle `label-md` weight.

### Cards & Insight Modules
*   **Rule:** Forbid all dividers. 
*   **Style:** Use `surface-container-low` as the card base. Group related data using vertical whitespace from the Spacing Scale (typically 24px or 32px).
*   **Wellbeing "Pulse" Component:** A signature component for this system—a soft, glowing gradient orb using `primary-fixed-dim` that subtly pulses behind key AI insights to represent the "living" nature of the system.

### Input Fields
*   **Style:** Minimalist. Use `surface-container-lowest` as the fill. 
*   **Focus State:** Instead of a heavy border, use a subtle 2px glow of `primary-container` and transition the label color to `primary`.

### Chips (Sentiment & Status)
*   **Style:** High-legibility `label-md` text inside a `secondary-container` (#c1edd1) for positive states or `tertiary-container` (#dbf5fd) for neutral reflection.

---

## 6. Do’s and Don’ts

### Do:
*   **Embrace the "Dead Space":** Use large margins to allow the student’s mind to rest. 
*   **Use Soft Asymmetry:** Offset a headline to the left while keeping the body text centered in a narrower column to create an editorial feel.
*   **Layer Surfaces:** Use the `surface-container` tiers to create hierarchy.

### Don’t:
*   **Don't use 100% black text:** Always use `on-surface` (#05345c) to maintain a soft, premium feel.
*   **Don't use sharp corners:** Never go below the `DEFAULT` (0.5rem) radius. Wellbeing is soft, not jagged.
*   **Don't use "clinical" blue:** Avoid high-vibrancy, "tech" blues. Stick to our muted `primary` (#266774) and `tertiary` (#4b6369) tones.
*   **Don't use dividers:** If you feel the need for a line, use 48px of whitespace instead.