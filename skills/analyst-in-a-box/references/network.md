# The knowledge page

[中文](network.zh.md)

`network` turns a workspace into one HTML page, `knowledge.html`: the business knowledge graph as a moving network.
It has two parts, the metric tree and the business world description. The page reads `model.yaml` and `world.yaml`
and draws what is in them. It adds no node and no claim.

Contents: 1 Command · 2 What is drawn · 3 Trust tiers · 4 Using the page · 5 Limits

## 1. Command

```
python scripts/aib_cli.py network --workspace <dir> [--lang zh|en] [--out FILE]
```

Writes `<dir>/knowledge.html` and prints how many cards and links each view has. `--lang` defaults to the workspace
language. The file is self-contained: inline style, script and data, no network, no web fonts. It opens from `file://`.
Run it again after the workspace changes; the page is rebuilt from the YAML and never edited by hand.

## 2. What is drawn

| View | Cards | Links |
|---|---|---|
| Metric tree | every metric (the north star first), and every dimension named in a cut order | formulas (`identities`: a left metric to each factor, with × or ÷), always visible; cut order (`priorities`: a metric to a dimension, numbered), shown only for the card that is hovered, focused or tapped |
| Business world description | entities, mechanisms, events, actions | `relations` between entities; each mechanism, event and action to the entities it names |

Events are pulled toward a date axis by their start date. Dimensions a metric can be cut by but that have no recorded
order are listed in the detail panel, not drawn.

## 3. Trust tiers

The tier of a card or link comes only from `source.kind` and `status` of its own record:

| Tier | Rule | Look |
|---|---|---|
| Fact | `source.kind` is `user`, `system_record`, `data` or `formula`, and `status` is `confirmed` | solid outline, blue fill, tick |
| To confirm | `status` is `proposed`, or `source.kind` is `document` | dashed outline, "to confirm" badge, the quoted sentence in the panel |
| AI inference | `source.kind` is `general_knowledge` or `demo_setting` | dotted outline, light fill, "inference" badge |
| Retired | `status` is `retired` (wins over the others) | grey, struck through |
| No source recorded | a metric that no formula record names; there is no claim for a person to confirm | neutral grey dash-dot outline, "no source" badge |

Inference stays inference even when marked `confirmed`. A record with no usable source is shown as "to confirm", never
as a fact. A metric has no source of its own: it takes the weakest tier of the formulas it appears in, and says so. A metric that appears in no formula is "no source recorded": the model uses it, but no record says where it came from.
A dimension takes the weakest tier of the cut orders that name it. The legend explains the tiers and a switch hides AI inference.

A demo workspace's settings (`demo_setting`) are shown as AI inference on purpose, until a person confirms them.

## 4. Using the page

- Drag a card to move it; the layout warms up for a moment and settles again. Drag the background to pan, wheel or pinch to zoom.
- Click a card or a link, or Tab to a card and press Enter: the panel shows the label, kind, source (with the quote and
  date when the record has them), status, and "what data would refute it" when `refuted_by` is set.
- Hovering or focusing a card dims everything except its neighbours. In the metric tree this is also how the cut links appear; they are hidden otherwise, so the formula tree reads cleanly. The panel lists the cut order ("1 Region, 2 Channel") for a metric, and for a dimension the metrics it cuts with its position in each. Esc closes the panel.
- With `prefers-reduced-motion` the settled layout is drawn at once.

## 5. Limits

The page shows the records as they are. It does not check them against the data; use `check` for that. Long sentences
are cut to two lines on the card and shown whole in the panel.
