# Pory Companion — Dev Notes for Claude

## Recent changes (v1.0.6)

### Tournament timer — fullscreen button layout
`poke-companion/pory_companion.py` ~line 1651

The fullscreen button was originally on its own row below the Start/Pause/Reset buttons
(`row=1, column=0, columnspan=3`). It was moved onto the same row as the other controls
(`row=0, column=3`) so all four buttons appear in a single horizontal line.

---

## Build notes

### PIL / Pillow error on launch
**Error:** `ModuleNotFoundError: No module named 'PIL'`

**Cause:** Pillow was not installed in the Python environment before running PyInstaller,
so it was not bundled into the exe. The script imports PIL at the top of the file.

**Fix:** Install Pillow first, then rebuild:
```
pip install pillow
python -m PyInstaller --onefile --windowed --name "pory_companion" \
    --add-data "pory.gif;." \
    --add-data "pory B.gif;." \
    --add-data "S_pory.gif;." \
    --add-data "S_pory B.gif;." \
    --add-data "budew.gif;." \
    --add-data "budew B.gif;." \
    --add-data "timerBG.png;." \
    --add-data "version.txt;." \
    pory_companion.py
```

Run the above from inside the `poke-companion/` folder. The finished exe lands in `poke-companion/dist/`.

### Required pip packages before building
```
pip install pillow pyinstaller
```
