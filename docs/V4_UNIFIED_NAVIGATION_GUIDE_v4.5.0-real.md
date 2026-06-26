# Unified Navigation Guide - v4.5.0-real

v4.5 fixes duplicated Unified Surface rendering. The left sidebar now keeps one desktop `Unified Surface` group, while mobile drawer headings are intentionally labelled with a `Mobile -` prefix so duplicate identical headings do not appear in the DOM.

## Sections

The global navigation can expose distinct sections such as Unified Surface, AI and Research, Live / Safety, and Platform / Settings. Sections must not duplicate the same heading unless they are intentionally different UI regions with distinct labels.

## Regression Guard

Tests assert that the sidebar does not contain duplicate identical `Unified Surface` headings and that `app/ui.py` does not insert a second Unified Surface section after the canonical nav list is declared.

Aliases remain navigation-only and do not bypass live-trading safety behavior.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
