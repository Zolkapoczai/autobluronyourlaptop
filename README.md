# Auto blur on your laptop

Windowsos adatvédelmi segéd: a webkamerán figyeli az arcodat, és **elmossa a képernyőt**, ha elfordulsz, vagy ha nem te ülsz a gép előtt.

## Működés
- **Arcdetektálás:** [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet). A szemek és az orr helyzetéből becsüli a fej elfordulását (yaw).
- **Arcfelismerés:** [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface). Csak a regisztrált tulajdonosnak nyílik ki (koszinusz-hasonlóság ≥ 0,363).
- **Elmosás:** a fő monitort egy mindig felül lévő, átkattintható overlay fedi le. Az elmosott kép képernyőképből készül, és maga az overlay ki van zárva a rögzítésből (`WDA_EXCLUDEFROMCAPTURE`).
- **Mikor mos el:** ha az arc 60°-nál jobban elfordul, ha idegen arcot lát, vagy ha nincs arc a kamera előtt.

## Telepítés
```bash
pip install -r requirements.txt
python blur.py --enroll   # egyszeri arcregisztráció, egyenesen a kamerába nézve
python blur.py            # indítás
```
Kilépés: **Ctrl+Shift+Q**

Automatikus indítás a Windows-szal: tegyél egy parancsikont a `shell:startup` mappába, amely ezt futtatja: `pythonw.exe "<útvonal>\blur.py"`.

## Beállítások (`blur.py` eleje)
| Konstans | Alapérték | Jelentés |
|---|---|---|
| `YAW_LIMIT` | 60 | Ennyi fok elfordulás után mos el |
| `NOSE_DEPTH` | 0.55 | A szögbecslés kalibrációja |
| `MATCH_THRESHOLD` | 0.363 | Az arcfelismerés küszöbe (magasabb = szigorúbb) |
| `DEBUG` | False | Képkockánként kiírja a mért szöget és az egyezést |

## Korlátok
- Csak a fő monitort mossa el.
- Nincs élőség-ellenőrzés, ezért fotóval vagy videóval megtéveszthető. **Nem biztonsági határ.**
- A regisztrált arc-lenyomat (`owner.npy`) biometrikus adat, csak helyben tárolódik, és a git nem követi (`.gitignore`).

## Követelmények
Windows 10 2004 vagy újabb, Python 3, webkamera. `opencv-python<5` kell, mert az OpenCV 5 API-ja eltér.

Modellek: YuNet (MIT) és SFace (Apache-2.0), mindkettő az [opencv_zoo](https://github.com/opencv/opencv_zoo) repóból.
