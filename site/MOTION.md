# Graph motion standard

[中文](MOTION.zh.md)

The graph moves like Obsidian's graph view. These are the numbers `tools/browser-check/check.mjs` measures
on every page that has a graph; a page fails the check if any is outside its range.

| Moment | What happens | Target | Accepted range |
|---|---|---|---|
| Opening | every node bursts from the centre on the first frame, then settles | ≈ 5 s to rest | 3.5 – 6.5 s |
| Dragging a node | its neighbours are pulled along by their links | — | — |
| Releasing a dragged node | the graph settles again | ≈ 4 s to rest | 2.5 – 5.5 s |
| Clicking a node | highlight and a light bounce; nothing moves | 0 px movement | ≤ 1 px |

## How the numbers arise

In `site/assets/graph.js`: one tick per 16.7 ms of wall time (so 60 Hz and 120 Hz screens behave the same);
the energy `alpha` decays toward its target by `1 − 0.001^(1/300)` per tick, i.e. 300 ticks ≈ 5 s from 1 to
rest; a drag holds the target at 0.3, and after release `alpha` falls from 0.3 to rest in ≈ 248 ticks ≈ 4.1 s.
Velocity keeps 60% per tick. Spacing scales with the panel size, and the drawing is kept centred except
while a node is held.

## Changing it

Change the motion only by changing these constants and re-running the check; never by eye.
