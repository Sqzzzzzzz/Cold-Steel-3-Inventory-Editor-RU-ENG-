# Changelog

## 7.0 — 2026-10-25

- Atomic bulk inventory updates: a group change now validates the save table once instead of repeatedly per item.
- Regression tests for rollback, preserving non-inventory data, larger batches and language UI.
- Corrected version label and late-added English translations; fixed the quantity-range error message.
- Rechecked original icon selection by ID and identified one missing cache asset (`Booster`) in the submitted user asset sample.
- Added release documentation and CI checks for the public source variant.
- Added an offline asset audit command for checking icon caches and explicit missing files.
- Removed silent Pillow installation from the normal Windows launcher; dependency installation is now opt-in.

## 6.5

- Exact U-Material icon for item ID 60.

## 6.4

- Included original English catalog in the private/offline owner edition; source releases load legally owned game tables at runtime.

## 6.3

- Added multi-select item editing and corrected specific Russian DLC strings.
