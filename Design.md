# Client Acquisition Tool — Complete Design System

## 1. Design Philosophy

The application should feel:

* premium
* modern
* clean
* professional
* focused
* spacious
* visual
* trustworthy
* fast

It should feel like a serious internal sales/productivity tool.

Avoid:

* neon colors
* excessive gradients
* excessive glassmorphism
* oversized cards
* huge shadows
* excessive rounded corners
* generic AI dashboard styling

---

# 2. Typography

Primary font:

```text
Inter
```

Weights:

```text
400 Regular
500 Medium
600 Semibold
700 Bold
```

Typography scale:

| Token      | Size | Line Height | Weight |
| ---------- | ---: | ----------: | -----: |
| Display XL | 48px |        56px |    700 |
| Display LG | 40px |        48px |    700 |
| H1         | 32px |        40px |    700 |
| H2         | 24px |        32px |    600 |
| H3         | 20px |        28px |    600 |
| H4         | 16px |        24px |    600 |
| Body Large | 16px |        24px |    400 |
| Body       | 14px |        21px |    400 |
| Small      | 13px |        18px |    400 |
| Caption    | 12px |        16px |    400 |

Use sentence case.

Avoid excessive uppercase text.

---

# 3. Primary Color

Primary:

```text
#4F46E5
```

Hover:

```text
#4338CA
```

Primary scale:

```text
50   #EEF2FF
100  #E0E7FF
200  #C7D2FE
300  #A5B4FC
400  #818CF8
500  #6366F1
600  #4F46E5
700  #4338CA
800  #3730A3
900  #312E81
```

---

# 4. Neutral Colors

```text
White       #FFFFFF
Background  #F8F9FB
Surface     #FFFFFF

Gray 50     #F9FAFB
Gray 100    #F3F4F6
Gray 200    #E5E7EB
Gray 300    #D1D5DB
Gray 400    #9CA3AF
Gray 500    #6B7280
Gray 600    #4B5563
Gray 700    #374151
Gray 800    #1F2937
Gray 900    #111827

Ink         #0B0F19
```

---

# 5. Semantic Colors

```text
Success     #10B981
Warning     #F59E0B
Danger      #EF4444
Info        #3B82F6
```

Do not use semantic colors as decorative colors.

---

# 6. Spacing

Use a 4px spacing system:

```text
4px
8px
12px
16px
20px
24px
32px
40px
48px
64px
80px
96px
```

---

# 7. Border Radius

```text
Inputs / Buttons      8px
Cards                 12px
Feature Panels        16px
```

Do not use extremely rounded components throughout the interface.

---

# 8. Shadows

Prefer borders over shadows.

Small:

```css
0 1px 2px rgba(16,24,40,.04)
```

Medium:

```css
0 4px 12px rgba(16,24,40,.06)
```

Large:

```css
0 12px 32px rgba(16,24,40,.08)
```

Use shadows sparingly.

---

# 9. Application Layout

Desktop:

```text
Sidebar: 248px
Topbar: 64px
Main padding: 32–40px
Max content width: 1440px
```

Structure:

```text
┌──────────────────────────────────────┐
│ Sidebar │ Topbar                     │
│         ├────────────────────────────┤
│         │ Page Header                 │
│         │                             │
│         │ Filters / Actions           │
│         │                             │
│         │ Main Content                │
│         │                             │
└─────────┴────────────────────────────┘
```

---

# 10. Buttons

## Primary

```text
Height: 40px
Padding: 0 16px
Radius: 8px
Font: 14px / 600
Background: #4F46E5
```

Hover:

```text
#4338CA
```

## Secondary

```text
Background: #FFFFFF
Border: #D1D5DB
Text: #374151
```

## Ghost

```text
Background: transparent
Text: #4B5563
Hover: #F3F4F6
```

Icon buttons:

```text
40 × 40px
```

---

# 11. Inputs

```text
Height: 40px
Radius: 8px
Border: #D1D5DB
Horizontal Padding: 12px
Font: 14px
```

Focus:

```text
Border: #6366F1
Subtle focus ring
```

Every input must have an accessible label.

---

# 12. Cards

Default card:

```text
Background: #FFFFFF
Border: 1px solid #E5E7EB
Radius: 12px
Padding: 24px
```

Cards should be used to group related information, not every small piece of UI.

---

# 13. Tables

Header:

```text
Background: #F9FAFB
Font: 12px / 600
Color: #6B7280
```

Rows:

```text
~64px height
Horizontal separators
Hover state
```

Tables should support:

* loading
* empty
* error
* pagination

---

# 14. Status Badges

Recommended semantic mapping:

```text
New             Gray
Qualified       Indigo
Contacted       Blue
Replied         Green
Meeting         Orange
Won             Green
Lost            Red
```

Use:

```text
Tinted Background
+
Readable Text
```

Do not communicate status only through color.

---

# 15. Sidebar

Width:

```text
248px
```

Active navigation:

```text
Background: #EEF2FF
Text: #4338CA
```

Use:

```text
Icon + Label
```

Mobile:

```text
Drawer
+
Overlay
```

---

# 16. Icons

Use:

```text
Lucide React
```

Sizes:

```text
Small: 16px
Default: 18px
Large: 20–24px
```

Icons should support text rather than replace important labels.

---

# 17. Motion

Use Framer Motion.

Default duration:

```text
150–200ms
```

Use motion for:

* page transitions
* dialogs
* drawers
* toasts
* Kanban movement
* generation states
* subtle hover effects

Avoid unnecessary animation.

Respect reduced-motion preferences.

---

# 18. Responsive Breakpoints

```text
sm    640px
md    768px
lg    1024px
xl    1280px
2xl   1536px
```

Required testing:

```text
320
375
390
414
768
1024
1280
1440
1920
```

---

# 19. Responsive Rules

## Mobile

* sidebar → drawer
* tables → cards
* forms → one column
* filters → drawer/sheet
* mockup controls → stacked
* touch targets ≥44px
* no horizontal overflow

## Tablet

* retain two-column layouts when useful
* reduce padding
* collapse secondary actions

## Desktop

* use split layouts for audit/mockup screens
* use available horizontal space
* maintain readable line lengths

---

# 20. Accessibility

Target:

```text
WCAG AA
```

Requirements:

* semantic HTML
* keyboard navigation
* visible focus
* accessible labels
* accessible dialogs
* accessible dropdowns
* sufficient contrast
* screen-reader states
* color-independent status
* reduced motion

---

# 21. Component Library

## Foundation

```text
Button
Input
Textarea
Select
Checkbox
Radio
Switch
Badge
Avatar
Tooltip
Divider
Spinner
Skeleton
```

## Layout

```text
AppShell
Sidebar
Topbar
PageHeader
Section
Container
Stack
Grid
```

## Data

```text
DataTable
Pagination
FilterBar
SearchInput
EmptyState
StatCard
StatusBadge
```

## Product

```text
LeadCard
LeadTable
LeadScore
AuditScore
AuditIssue
MockupCard
MockupViewer
OutreachEditor
ActivityTimeline
PipelineColumn
PipelineCard
FollowupCard
```

---

# 22. Visual Priority

Highest visual quality should be given to:

```text
1. Lead Details
2. Mockup Studio
3. Outreach Studio
```

The dashboard should remain useful and calm.

---

# 23. Dark Mode

Dark mode should use semantic design tokens.

Do not simply invert colors.

Dark mode should have:

* dark application background
* elevated surfaces
* subtle borders
* readable primary text
* muted secondary text
* visible icons
* appropriate primary accent

Implement after the light design system is stable.
