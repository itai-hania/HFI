# HFI Dashboard UX E2E Checklist

## Purpose
Manual verification checklist for end-to-end UI/UX quality on desktop and tablet breakpoints.

## Environments
- Local: `http://localhost:8501`
- Browser: Chrome (latest)
- Viewports:
1. `1440 x 900`
2. `1024 x 768`
3. `768 x 1024`

## Core Flows
1. Login
- [ ] Login screen appears when auth is enabled.
- [ ] Valid password enters dashboard.
- [ ] Invalid password shows clear error.
- [ ] Lockout message appears after repeated failures.

2. Discovery and Queue
- [ ] Home renders `Ready to Publish`, `Discovered Trends`, `Processed Threads`.
- [ ] Add trend to queue shows success feedback.
- [ ] Generate from trend routes to Content > Generate.
- [ ] Delete trend action is visible and explicit.

3. Acquire
- [ ] Scrape form has visible labels.
- [ ] Blank scrape submit shows inline validation.
- [ ] Cooldown text appears when scrape is rate-limited.
- [ ] Successful scrape shows confirmation.

4. Queue and Review
- [ ] Queue action bar shows `Translate All`, `Approve All`, `Status filter`.
- [ ] Empty queue shows text-first empty state.
- [ ] Edit view shows original and Hebrew content with visible labels.
- [ ] Save/Approve/Delete actions provide clear feedback.

5. Generate
- [ ] Single post generation flow works.
- [ ] Thread generation flow works.
- [ ] Approve and draft actions are clearly distinguished.

6. Publish Handoff
- [ ] Publish section appears in Content routing.
- [ ] Approved items are listed for handoff.
- [ ] `Set Scheduled Time` updates schedule.
- [ ] `Mark as Published` sets published state.
- [ ] `Return to Review` sets processed state.

## Accessibility
1. Keyboard and Focus
- [ ] Tabbing reaches navigation, form controls, and action buttons.
- [ ] Focus ring is clearly visible on interactive elements.
- [ ] No primary inputs rely on placeholder-only labels.

2. Motion and Visual
- [ ] Reduced motion preference disables non-essential animation.
- [ ] No emoji-only controls are used for critical actions.
- [ ] Contrast remains readable in all major sections.

## Regression Notes
- Log failures with:
1. View + action name
2. Expected behavior
3. Actual behavior
4. Screenshot path
