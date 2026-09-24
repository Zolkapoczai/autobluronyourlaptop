# Auto blur on your laptop

Adatvédelmi segéd: a webkamerán figyeli az arcodat, és **elmossa a képernyőt**, ha elfordulsz, vagy ha nem te ülsz a gép előtt.

| Platform | Mappa | Indítás | Állapot |
|---|---|---|---|
| 🪟 **Windows** | [`windows/`](windows/) | `python blur.py` | tesztelve |
| 🍎 **macOS** | [`mac/`](mac/) | `python3 blur_mac.py` | **nincs tesztelve** (Windowson készült) |

A közös modellek a [`models/`](models/) mappában vannak.

## Működés (mindkét verzió)
- **Arcdetektálás:** [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet). A szemek és az orr helyzetéből becsüli a fej elfordulását (yaw).
- **Arcfelismerés:** [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface). Csak a regisztrált tulajdonosnak nyílik ki (koszinusz-hasonlóság ≥ 0,363).
- **Mikor mos el:** ha az arc 60°-nál jobban elfordul, ha idegen arcot lát, vagy ha nincs arc a kamera előtt.

---

## 🪟 Windows (`windows/`)
Windows 10 2004 vagy újabb, Python 3, webkamera.
```bash
cd windows
pip install -r requirements.txt
python blur.py --enroll   # egyszeri arcregisztráció, egyenesen a kamerába nézve
python blur.py
```
- **Elmosás:** a fő monitort egy mindig felül lévő, átkattintható overlay fedi le. Az elmosott kép képernyőképből készül, és maga az overlay ki van zárva a rögzítésből (`WDA_EXCLUDEFROMCAPTURE`).
- **Kilépés:** **Ctrl+Shift+Q**
- **Automatikus indítás:** tegyél egy parancsikont a `shell:startup` mappába, amely ezt futtatja: `pythonw.exe "<útvonal>\windows\blur.py"`.
- **Korlát:** csak a fő monitort mossa el.

## 🍎 macOS (`mac/`)
macOS 11 vagy újabb, Python 3, webkamera.
```bash
cd mac
pip3 install -r requirements.txt
python3 blur_mac.py --enroll
python3 blur_mac.py
```
- **Elmosás:** natív `NSVisualEffectView` ablak minden monitoron. Élőben mossa el a tartalmat, képernyőrögzítési engedély nem kell hozzá.
- **Kilépés:** a menüsorban a **Blur → Quit**, vagy Ctrl+C a terminálban.
- **Automatikus indítás:** `sh install_autostart.sh` (LaunchAgent).
- **Kameraengedély:** első indításkor a macOS engedélyt kér (Rendszerbeállítások → Adatvédelem → Kamera). LaunchAgentből indítva lehet, hogy a Python binárisnak külön engedély kell.
- **Korlát:** az elmosás erőssége fix (rendszer-anyag), nem állítható.

---

## Beállítások (a `.py` fájlok elején)
| Konstans | Alapérték | Jelentés |
|---|---|---|
| `YAW_LIMIT` | 60 | Ennyi fok elfordulás után mos el |
| `NOSE_DEPTH` | 0.55 | A szögbecslés kalibrációja |
| `MATCH_THRESHOLD` | 0.363 | Az arcfelismerés küszöbe (magasabb = szigorúbb) |
| `DEBUG` | False | Képkockánként kiírja a mért szöget és az egyezést |

## Korlátok és biztonság
- Nincs élőség-ellenőrzés, ezért fotóval vagy videóval megtéveszthető. **Nem biztonsági határ.**
- A regisztrált arc-lenyomat (`owner.npy`) biometrikus adat, csak helyben tárolódik, és a git nem követi (`.gitignore`).
- `opencv-python<5` kell, mert az OpenCV 5-ből kikerült a `CascadeClassifier`, és az API-ja is eltér.

Modellek: YuNet (MIT) és SFace (Apache-2.0), mindkettő az [opencv_zoo](https://github.com/opencv/opencv_zoo) repóból.
