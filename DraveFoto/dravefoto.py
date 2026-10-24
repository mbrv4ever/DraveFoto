# -*- coding: utf-8 -*-
# DraveFoto - foto's bekijken, sorteren op datum en dubbele foto's vinden.
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Vrije software onder de GNU GPL v3.0.
"""DraveFoto: orde in je foto's.

- Map kiezen -> grote miniaturen. Dubbelklik = groot bekijken (pijltjes = volgende/vorige).
- Sorteren op datum: zet foto's in mappen Jaar\\Maand (kopiëren of verplaatsen), met eerst een voorbeeld.
- Dubbele foto's vinden (precies dezelfde inhoud) -> naar een map '_dubbel' (niets wordt gewist).
- Hernoemen op datum: '2026-10-21 14.03.22.jpg'.
- Draaien, favoriet (kopie naar 'Favorieten'), weggooien = naar de Prullenbak.
"""
import datetime
import hashlib
import json
import os
import shutil
import sys

from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QImage, QKeySequence, QShortcut, QTransform
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                             QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QDialog, QRadioButton,
                             QCheckBox, QComboBox, QTextEdit, QProgressBar, QSlider, QButtonGroup, QMenu)

try:
    from PIL import Image, ImageOps
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except Exception:
        pass
except Exception:  # zonder Pillow werkt bekijken nog wel (via Qt)
    Image = None

APP_NAAM = "DraveFoto"
APP_VERSION = "1.0.1"
FOTO = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".heic", ".heif")
MAANDEN = ["01 januari", "02 februari", "03 maart", "04 april", "05 mei", "06 juni", "07 juli", "08 augustus",
           "09 september", "10 oktober", "11 november", "12 december"]
BG, PANEL, ZILVER, GRIJS, ACCENT, GOUD = "#0e0e11", "#16161b", "#e6e6ea", "#8a8a94", "#6fa3d6", "#ffb347"


def app_map():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def bron(naam):
    for b in (getattr(sys, "_MEIPASS", None), app_map()):
        if b and os.path.exists(os.path.join(b, naam)):
            return os.path.join(b, naam)
    return os.path.join(app_map(), naam)


def data_map():
    p = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DraveFoto")
    os.makedirs(p, exist_ok=True)
    return p


CFG = os.path.join(data_map(), "instellingen.json")


def lees_cfg():
    c = dict(map=os.path.join(os.path.expanduser("~"), "Pictures"), grootte=220)
    try:
        with open(CFG, encoding="utf-8-sig") as f:
            c.update(json.load(f))
    except Exception:
        pass
    return c


def bewaar_cfg(c):
    try:
        with open(CFG, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ------------------------------------------------------------------ hulp
def naar_prullenbak(pad):
    """Bestand naar de Windows-Prullenbak (terug te halen)."""
    try:
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
        op = SHFILEOPSTRUCTW(None, 3, os.path.abspath(pad) + "\0\0", None, 0x0040 | 0x0010 | 0x0400 | 0x0004, False, None, None)
        return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0
    except Exception:
        return False


def datum_van(pad):
    """Opnamedatum uit de foto (EXIF), anders de wijzigingsdatum van het bestand."""
    if Image is not None:
        try:
            with Image.open(pad) as im:
                ex = im.getexif()
                t = None
                try:
                    t = ex.get_ifd(0x8769).get(36867)  # DateTimeOriginal
                except Exception:
                    pass
                t = t or ex.get(36867) or ex.get(306)  # DateTime
                if t:
                    return datetime.datetime.strptime(str(t).strip()[:19], "%Y:%m:%d %H:%M:%S"), True
        except Exception:
            pass
    return datetime.datetime.fromtimestamp(os.path.getmtime(pad)), False


def vrije_naam(doel):
    if not os.path.exists(doel):
        return doel
    stam, ext = os.path.splitext(doel)
    n = 2
    while os.path.exists("%s (%d)%s" % (stam, n, ext)):
        n += 1
    return "%s (%d)%s" % (stam, n, ext)


def laad_qimage(pad, maxkant=None):
    """Foto laden, rechtop gezet volgens EXIF; ook HEIC (als pillow-heif er is)."""
    if Image is not None:
        try:
            with Image.open(pad) as im:
                im = ImageOps.exif_transpose(im)
                if maxkant:
                    im.thumbnail((maxkant, maxkant))
                im = im.convert("RGBA")
                data = im.tobytes("raw", "RGBA")
                q = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
                return q.copy()
        except Exception:
            pass
    q = QImage(pad)
    if maxkant and not q.isNull():
        q = q.scaled(maxkant, maxkant, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return q


def fotos_in(map_, sub=False):
    uit = []
    if sub:
        for r, ds, fs in os.walk(map_):
            ds[:] = [d for d in ds if not d.startswith((".", "_dubbel"))]
            uit += [os.path.join(r, f) for f in fs if f.lower().endswith(FOTO)]
    else:
        try:
            uit = [os.path.join(map_, f) for f in os.listdir(map_) if f.lower().endswith(FOTO)]
        except Exception:
            pass
    return sorted(uit, key=lambda p: p.lower())


# ------------------------------------------------------------------ achtergrondwerk
class Miniaturen(QThread):
    klaar = pyqtSignal(int, QImage)

    def __init__(self, paden, kant):
        super().__init__()
        self.paden, self.kant, self.stop = paden, kant, False

    def run(self):
        for i, p in enumerate(self.paden):
            if self.stop:
                return
            self.klaar.emit(i, laad_qimage(p, self.kant))


class Werk(QThread):
    """Voert een lijst (bron, doel, soort) uit: soort = kopie | verplaats."""
    voortgang = pyqtSignal(int, int)
    gedaan = pyqtSignal(int, list)

    def __init__(self, taken):
        super().__init__()
        self.taken = taken

    def run(self):
        ok, fout = 0, []
        for i, (b, d, soort) in enumerate(self.taken):
            try:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                d = vrije_naam(d)
                if soort == "kopie":
                    shutil.copy2(b, d)
                else:
                    shutil.move(b, d)
                ok += 1
            except Exception as e:
                fout.append("%s: %s" % (os.path.basename(b), e))
            self.voortgang.emit(i + 1, len(self.taken))
        self.gedaan.emit(ok, fout)


class Plannen(QThread):
    """Datums of hashes uitrekenen (kan even duren bij veel foto's)."""
    voortgang = pyqtSignal(int, int)
    gedaan = pyqtSignal(list)

    def __init__(self, paden, soort):
        super().__init__()
        self.paden, self.soort = paden, soort

    def run(self):
        uit = []
        for i, p in enumerate(self.paden):
            try:
                if self.soort == "datum":
                    uit.append((p,) + datum_van(p))
                else:
                    h = hashlib.md5()
                    with open(p, "rb") as f:
                        for blok in iter(lambda: f.read(1 << 20), b""):
                            h.update(blok)
                    uit.append((p, os.path.getsize(p), h.hexdigest()))
            except Exception:
                pass
            self.voortgang.emit(i + 1, len(self.paden))
        self.gedaan.emit(uit)


# ------------------------------------------------------------------ voorbeeld-venster
class Voorbeeld(QDialog):
    def __init__(self, ouder, titel, uitleg, regels, knop):
        super().__init__(ouder)
        self.setWindowTitle(titel)
        self.resize(900, 620)
        l = QVBoxLayout(self)
        u = QLabel(uitleg)
        u.setWordWrap(True)
        l.addWidget(u)
        t = QTextEdit()
        t.setReadOnly(True)
        t.setPlainText("\n".join(regels[:3000]) + ("\n... en nog %d" % (len(regels) - 3000) if len(regels) > 3000 else ""))
        l.addWidget(t, 1)
        rij = QHBoxLayout()
        rij.addStretch(1)
        nee = QPushButton("Annuleren")
        nee.clicked.connect(self.reject)
        ja = QPushButton(knop)
        ja.setObjectName("hoofd")
        ja.clicked.connect(self.accept)
        rij.addWidget(nee)
        rij.addWidget(ja)
        l.addLayout(rij)


class SorteerKeuze(QDialog):
    def __init__(self, ouder, bronmap):
        super().__init__(ouder)
        self.setWindowTitle("Sorteren op datum")
        l = QVBoxLayout(self)
        l.addWidget(QLabel("De foto's komen in mappen per jaar en maand, bijvoorbeeld:\n2026\\10 oktober\\"))
        self.kopie = QRadioButton("Kopiëren (de originelen blijven staan) - veiligst")
        self.verplaats = QRadioButton("Verplaatsen (de foto's gaan uit de oude map)")
        self.kopie.setChecked(True)
        g = QButtonGroup(self)
        g.addButton(self.kopie)
        g.addButton(self.verplaats)
        l.addWidget(self.kopie)
        l.addWidget(self.verplaats)
        self.hernoem = QCheckBox("Ook een nieuwe naam geven met datum en tijd (2026-10-21 14.03.22.jpg)")
        l.addWidget(self.hernoem)
        self.sub = QCheckBox("Ook foto's in submappen meenemen")
        l.addWidget(self.sub)
        self.doel = os.path.join(bronmap, "Gesorteerd")
        self.doel_lbl = QLabel()
        self._zet_doel()
        l.addWidget(self.doel_lbl)
        k = QPushButton("Andere doelmap kiezen...")
        k.clicked.connect(self._kies)
        l.addWidget(k)
        rij = QHBoxLayout()
        rij.addStretch(1)
        n = QPushButton("Annuleren")
        n.clicked.connect(self.reject)
        j = QPushButton("Voorbeeld tonen")
        j.setObjectName("hoofd")
        j.clicked.connect(self.accept)
        rij.addWidget(n)
        rij.addWidget(j)
        l.addLayout(rij)

    def _zet_doel(self):
        self.doel_lbl.setText("Doelmap: " + self.doel)

    def _kies(self):
        d = QFileDialog.getExistingDirectory(self, "Doelmap", self.doel)
        if d:
            self.doel = d
            self._zet_doel()


# ------------------------------------------------------------------ groot bekijken
class Kijker(QDialog):
    def __init__(self, ouder, paden, i):
        super().__init__(ouder)
        self.ouder, self.paden, self.i = ouder, paden, i
        self.setWindowTitle("DraveFoto")
        self.setStyleSheet("background:#000; color:%s; font-size:18px;" % ZILVER)
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.beeld = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.beeld.setMinimumSize(200, 200)
        l.addWidget(self.beeld, 1)
        self.info = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.info.setStyleSheet("padding:8px; background:%s;" % PANEL)
        l.addWidget(self.info)
        self.q = None
        for toets, fn in (("Right", lambda: self.ga(1)), ("Left", lambda: self.ga(-1)), ("Space", lambda: self.ga(1)),
                          ("Escape", self.close), ("R", lambda: self.draai(90)), ("L", lambda: self.draai(-90)),
                          ("F", self.favoriet), ("Delete", self.weg), ("F11", self.wissel_vol)):
            QShortcut(QKeySequence(toets), self, activated=fn)
        self.showMaximized()
        self.laad()

    def laad(self):
        if not self.paden:
            self.close()
            return
        self.i = max(0, min(self.i, len(self.paden) - 1))
        p = self.paden[self.i]
        self.q = laad_qimage(p)
        d, echt = datum_van(p)
        self.info.setText("%d / %d   ·   %s   ·   %s%s   ·   ←/→ bladeren · R/L draaien · F favoriet · Delete weggooien · Esc sluiten"
                          % (self.i + 1, len(self.paden), os.path.basename(p), d.strftime("%d-%m-%Y %H:%M"),
                             "" if echt else " (bestandsdatum)"))
        self.toon()

    def toon(self):
        if self.q is None or self.q.isNull():
            self.beeld.setText("Deze foto kan ik niet openen.")
            return
        self.beeld.setPixmap(QPixmap.fromImage(self.q).scaled(self.beeld.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                              Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.toon()

    def ga(self, d):
        self.i = (self.i + d) % max(1, len(self.paden))
        self.laad()

    def wissel_vol(self):
        self.showMaximized() if self.isFullScreen() else self.showFullScreen()

    def draai(self, graden):
        if self.ouder.draai_bestand(self.paden[self.i], graden):
            self.laad()

    def favoriet(self):
        self.ouder.favoriet(self.paden[self.i])

    def weg(self):
        if self.ouder.weggooien([self.paden[self.i]]):
            self.paden.pop(self.i)
            self.laad()


# ------------------------------------------------------------------ hoofdvenster
class Foto(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = lees_cfg()
        self.setWindowTitle(APP_NAAM)
        self.setWindowIcon(QIcon(bron(os.path.join("assets", "icon.ico"))))
        self.resize(1400, 900)
        self.paden = []
        self.loader = None
        self.werk = None
        self._bouw()
        self.open_map(self.cfg["map"] if os.path.isdir(self.cfg["map"]) else os.path.expanduser("~"))

    def _bouw(self):
        w = QWidget()
        self.setCentralWidget(w)
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        balk = QWidget()
        balk.setObjectName("balk")
        b = QHBoxLayout(balk)
        b.setContentsMargins(12, 8, 12, 8)
        for tekst, fn in (("📁  Map kiezen", self.kies_map), ("⬆  Map omhoog", self.omhoog),
                          ("📅  Sorteren op datum", self.sorteer), ("🔍  Dubbele foto's", self.dubbel),
                          ("✏  Hernoemen op datum", self.hernoem_datum)):
            k = QPushButton(tekst)
            k.clicked.connect(fn)
            b.addWidget(k)
        b.addStretch(1)
        b.addWidget(QLabel("Grootte:"))
        self.schuif = QSlider(Qt.Orientation.Horizontal)
        self.schuif.setRange(120, 400)
        self.schuif.setValue(int(self.cfg["grootte"]))
        self.schuif.setFixedWidth(160)
        self.schuif.sliderReleased.connect(self._grootte)
        b.addWidget(self.schuif)
        for tekst, fn in (("?  Snelgids", self.snelgids),):
            k = QPushButton(tekst)
            k.clicked.connect(fn)
            b.addWidget(k)
        l.addWidget(balk)
        self.pad_lbl = QLabel()
        self.pad_lbl.setObjectName("pad")
        l.addWidget(self.pad_lbl)
        self.raster = QListWidget()
        self.raster.setViewMode(QListWidget.ViewMode.IconMode)
        self.raster.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.raster.setMovement(QListWidget.Movement.Static)
        self.raster.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.raster.setUniformItemSizes(True)
        self.raster.setSpacing(8)
        self.raster.itemActivated.connect(self._open)
        self.raster.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.raster.customContextMenuRequested.connect(self._menu)
        l.addWidget(self.raster, 1)
        self.balk = QProgressBar()
        self.balk.hide()
        l.addWidget(self.balk)
        self.statusBar().addPermanentWidget(QLabel("v" + APP_VERSION))
        for toets, fn in (("Delete", lambda: self.weggooien(self._gekozen())), ("Ctrl+O", self.kies_map),
                          ("Backspace", self.omhoog), ("F5", lambda: self.open_map(self.map)),
                          ("Ctrl+R", lambda: [self.draai_bestand(p, 90) for p in self._gekozen()] and self.open_map(self.map)),
                          ("F", lambda: [self.favoriet(p) for p in self._gekozen()])):
            QShortcut(QKeySequence(toets), self.raster, activated=fn)
        self.setStyleSheet("""
            QMainWindow { background:%(BG)s; } QWidget { color:%(Z)s; font-size:17px; }
            QWidget#balk { background:%(P)s; border-bottom:1px solid #26262e; }
            QLabel#pad { padding:6px 14px; color:%(G)s; background:%(BG)s; }
            QListWidget { background:%(BG)s; border:0; font-size:14px; }
            QListWidget::item { border-radius:8px; padding:4px; }
            QListWidget::item:selected { background:#2a3a52; }
            QPushButton { background:#24242c; border:1px solid #3a3a44; border-radius:8px; padding:8px 14px; font-size:16px; }
            QPushButton:hover { border-color:%(A)s; } QPushButton#hoofd { background:%(A)s; color:#0e0e11; font-weight:700; }
            QDialog, QTextEdit { background:%(P)s; } QStatusBar { background:%(P)s; color:%(G)s; }
            QProgressBar { background:%(P)s; border:0; height:22px; text-align:center; } QProgressBar::chunk { background:%(A)s; }
            QRadioButton::indicator, QCheckBox::indicator { width:22px; height:22px; border:2px solid %(G)s; background:#24242c; }
            QRadioButton::indicator { border-radius:13px; } QCheckBox::indicator { border-radius:5px; }
            QRadioButton::indicator:checked, QCheckBox::indicator:checked { background:%(A)s; border:2px solid %(Z)s; }
            QRadioButton { spacing:10px; } QCheckBox { spacing:10px; } /* indicator-1.0.1 */
            QMenu { background:%(P)s; border:1px solid #3a3a44; } QMenu::item:selected { background:#2a3a52; }
        """ % dict(BG=BG, P=PANEL, Z=ZILVER, G=GRIJS, A=ACCENT))

    # ---- map tonen
    def kies_map(self):
        d = QFileDialog.getExistingDirectory(self, "Map met foto's", self.map)
        if d:
            self.open_map(d)

    def omhoog(self):
        o = os.path.dirname(self.map.rstrip("\\/"))
        if o and o != self.map:
            self.open_map(o)

    def open_map(self, m):
        if self.loader:
            self.loader.stop = True
            self.loader.wait(2000)
        self.map = os.path.normpath(m)
        self.cfg["map"] = self.map
        bewaar_cfg(self.cfg)
        self.raster.clear()
        k = int(self.cfg["grootte"])
        self.raster.setIconSize(QSize(k, k))
        self.raster.setGridSize(QSize(k + 24, k + 44))
        # eerst submappen (dubbelklik = openen), dan foto's
        try:
            mappen = sorted(d for d in os.listdir(self.map) if os.path.isdir(os.path.join(self.map, d)) and not d.startswith("."))
        except Exception:
            mappen = []
        leeg = QPixmap(k, k)
        leeg.fill(Qt.GlobalColor.transparent)
        mapicoon = self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon)
        for d in mappen:
            it = QListWidgetItem(mapicoon, d)
            it.setData(Qt.ItemDataRole.UserRole, ("map", os.path.join(self.map, d)))
            self.raster.addItem(it)
        self.paden = fotos_in(self.map)
        self._eerste = len(mappen)
        for p in self.paden:
            it = QListWidgetItem(QIcon(leeg), os.path.basename(p)[:28])
            it.setToolTip(p)
            it.setData(Qt.ItemDataRole.UserRole, ("foto", p))
            self.raster.addItem(it)
        self.pad_lbl.setText("📁  %s     ·     %d foto's, %d mappen" % (self.map, len(self.paden), len(mappen)))
        self.loader = Miniaturen(list(self.paden), k)
        self.loader.klaar.connect(self._mini)
        self.loader.start()

    def _mini(self, i, q):
        it = self.raster.item(self._eerste + i)
        if it is not None and not q.isNull():
            it.setIcon(QIcon(QPixmap.fromImage(q)))

    def _grootte(self):
        self.cfg["grootte"] = self.schuif.value()
        self.open_map(self.map)

    def _gekozen(self):
        return [it.data(Qt.ItemDataRole.UserRole)[1] for it in self.raster.selectedItems()
                if it.data(Qt.ItemDataRole.UserRole)[0] == "foto"]

    def _open(self, it):
        soort, p = it.data(Qt.ItemDataRole.UserRole)
        if soort == "map":
            self.open_map(p)
        else:
            Kijker(self, list(self.paden), self.paden.index(p)).exec()
            self.open_map(self.map)

    def _menu(self, pos):
        g = self._gekozen()
        if not g:
            return
        m = QMenu(self)
        m.addAction("🔍  Groot bekijken", lambda: Kijker(self, list(self.paden), self.paden.index(g[0])).exec())
        m.addAction("⟳  Rechtsom draaien", lambda: ([self.draai_bestand(p, 90) for p in g], self.open_map(self.map)))
        m.addAction("⟲  Linksom draaien", lambda: ([self.draai_bestand(p, -90) for p in g], self.open_map(self.map)))
        m.addAction("⭐  Favoriet (kopie in 'Favorieten')", lambda: [self.favoriet(p) for p in g])
        m.addAction("📂  Tonen in Verkenner", lambda: os.system('explorer /select,"%s"' % g[0]))
        m.addSeparator()
        m.addAction("🗑  Weggooien (Prullenbak)", lambda: self.weggooien(g))
        m.exec(self.raster.mapToGlobal(pos))

    # ---- losse acties
    def draai_bestand(self, p, graden):
        if Image is None:
            return False
        try:
            with Image.open(p) as im:
                exif = im.info.get("exif")
                im = ImageOps.exif_transpose(im)
                im = im.rotate(-graden, expand=True)
                extra = dict(quality=95, subsampling="keep") if p.lower().endswith((".jpg", ".jpeg")) else {}
                if exif and p.lower().endswith((".jpg", ".jpeg")):
                    try:
                        e = Image.Exif()
                        e.load(exif)
                        e[0x0112] = 1  # nu rechtop
                        extra["exif"] = e.tobytes()
                    except Exception:
                        pass
                if extra.get("subsampling") == "keep":
                    extra.pop("subsampling")
                st = os.stat(p)
                tmp = p + ".draai.tmp" + os.path.splitext(p)[1]
                im.save(tmp, format=Image.registered_extensions().get(os.path.splitext(p)[1].lower()), **extra)
            os.replace(tmp, p)
            os.utime(p, (st.st_atime, st.st_mtime))
            return True
        except Exception as e:
            QMessageBox.warning(self, APP_NAAM, "Draaien lukt niet bij %s:\n%s" % (os.path.basename(p), e))
            return False

    def favoriet(self, p):
        doel = os.path.join(os.path.dirname(p), "Favorieten")
        os.makedirs(doel, exist_ok=True)
        shutil.copy2(p, vrije_naam(os.path.join(doel, os.path.basename(p))))
        self.statusBar().showMessage("⭐ Gekopieerd naar Favorieten: %s" % os.path.basename(p), 4000)

    def weggooien(self, paden):
        if not paden:
            return False
        if QMessageBox.question(self, "Weggooien", "%d foto('s) naar de Prullenbak?\n(Je kunt ze daar terughalen.)"
                                % len(paden)) != QMessageBox.StandardButton.Yes:
            return False
        weg = sum(1 for p in paden if naar_prullenbak(p))
        self.statusBar().showMessage("%d foto('s) naar de Prullenbak." % weg, 5000)
        QTimer.singleShot(0, lambda: self.open_map(self.map))
        return weg > 0

    # ---- grote klussen met voorbeeld
    def _plan(self, paden, soort, klaar):
        self.balk.setRange(0, max(1, len(paden)))
        self.balk.setValue(0)
        self.balk.setFormat("Foto's bekijken... %v / %m")
        self.balk.show()
        self.planner = Plannen(paden, soort)
        self.planner.voortgang.connect(lambda a, b: self.balk.setValue(a))
        self.planner.gedaan.connect(lambda r: (self.balk.hide(), klaar(r)))
        self.planner.start()

    def _voer_uit(self, taken, wat):
        self.balk.setRange(0, max(1, len(taken)))
        self.balk.setValue(0)
        self.balk.setFormat(wat + "... %v / %m")
        self.balk.show()
        self.werk = Werk(taken)
        self.werk.voortgang.connect(lambda a, b: self.balk.setValue(a))
        self.werk.gedaan.connect(self._klaar)
        self.werk.start()

    def _klaar(self, ok, fout):
        self.balk.hide()
        tekst = "Klaar: %d foto('s)." % ok
        if fout:
            tekst += "\n\nNiet gelukt (%d):\n%s" % (len(fout), "\n".join(fout[:15]))
        QMessageBox.information(self, APP_NAAM, tekst)
        self.open_map(self.map)

    def sorteer(self):
        k = SorteerKeuze(self, self.map)
        if not k.exec():
            return
        paden = fotos_in(self.map, k.sub.isChecked())
        doel = os.path.normpath(k.doel)
        paden = [p for p in paden if not os.path.normpath(p).startswith(doel + os.sep)]
        if not paden:
            QMessageBox.information(self, APP_NAAM, "Geen foto's gevonden in deze map.")
            return
        soort = "kopie" if k.kopie.isChecked() else "verplaats"

        def klaar(lijst):
            taken, regels, geen = [], [], 0
            for p, d, echt in lijst:
                geen += 0 if echt else 1
                naam = (d.strftime("%Y-%m-%d %H.%M.%S") + os.path.splitext(p)[1].lower()) if k.hernoem.isChecked() \
                    else os.path.basename(p)
                doelpad = os.path.join(doel, str(d.year), MAANDEN[d.month - 1], naam)
                taken.append((p, doelpad, soort))
                regels.append("%s  →  %s" % (os.path.relpath(p, self.map), os.path.relpath(doelpad, doel)))
            uitleg = ("%d foto's worden %s naar %s.\n%s" % (
                len(taken), "gekopieerd" if soort == "kopie" else "verplaatst", doel,
                ("Let op: bij %d foto's staat geen opnamedatum; daar gebruik ik de bestandsdatum." % geen) if geen else ""))
            if Voorbeeld(self, "Voorbeeld: sorteren", uitleg, regels, "Ja, doen").exec():
                self._voer_uit(taken, "Sorteren")
        self._plan(paden, "datum", klaar)

    def hernoem_datum(self):
        paden = self._gekozen() or self.paden
        if not paden:
            return

        def klaar(lijst):
            taken, regels = [], []
            for p, d, echt in lijst:
                nieuw = os.path.join(os.path.dirname(p), d.strftime("%Y-%m-%d %H.%M.%S") + os.path.splitext(p)[1].lower())
                if os.path.normcase(nieuw) != os.path.normcase(p):
                    taken.append((p, nieuw, "verplaats"))
                    regels.append("%s  →  %s%s" % (os.path.basename(p), os.path.basename(nieuw), "" if echt else "   (bestandsdatum)"))
            if not taken:
                QMessageBox.information(self, APP_NAAM, "Alle namen zijn al goed.")
                return
            if Voorbeeld(self, "Voorbeeld: hernoemen", "%d foto's krijgen een nieuwe naam:" % len(taken), regels,
                         "Ja, hernoemen").exec():
                self._voer_uit(taken, "Hernoemen")
        self._plan(paden, "datum", klaar)

    def dubbel(self):
        sub = QMessageBox.question(self, "Dubbele foto's", "Ook in de submappen zoeken?") == QMessageBox.StandardButton.Yes
        paden = fotos_in(self.map, sub)
        if not paden:
            QMessageBox.information(self, APP_NAAM, "Geen foto's gevonden.")
            return

        def klaar(lijst):
            groepen = {}
            for p, grootte, h in lijst:
                groepen.setdefault((grootte, h), []).append(p)
            taken, regels = [], []
            weg = os.path.join(self.map, "_dubbel")
            for (_, _), ps in groepen.items():
                if len(ps) < 2:
                    continue
                ps.sort(key=lambda x: (len(x), x.lower()))  # kortste naam/pad blijft staan
                regels.append("Blijft:  " + os.path.relpath(ps[0], self.map))
                for p in ps[1:]:
                    taken.append((p, os.path.join(weg, os.path.basename(p)), "verplaats"))
                    regels.append("   dubbel →  _dubbel\\" + os.path.basename(p) + "   (was " + os.path.relpath(p, self.map) + ")")
            if not taken:
                QMessageBox.information(self, APP_NAAM, "Geen dubbele foto's gevonden. 👍")
                return
            if Voorbeeld(self, "Dubbele foto's", "%d dubbele foto's gevonden. Ze gaan naar de map '_dubbel' (er wordt niets "
                         "gewist). Kijk ze daar na en gooi ze weg als je wilt." % len(taken), regels,
                         "Ja, naar _dubbel").exec():
                self._voer_uit(taken, "Opruimen")
        self._plan(paden, "hash", klaar)

    def snelgids(self):
        p = bron("DraveFoto-Snelgids.pdf")
        if os.path.exists(p):
            os.startfile(p)
        else:
            QMessageBox.information(self, "Snelgids", "Dubbelklik = groot bekijken. Rechtsklik = meer keuzes.")

    def closeEvent(self, e):
        if self.loader:
            self.loader.stop = True
            self.loader.wait(2000)
        e.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAAM)
    w = Foto()
    w.show()
    try:  # Dravenlock: stille update-check (uit te zetten; Ctrl+Shift+U = met de hand)
        import drave_update
        drave_update.start(w, "DraveFoto", APP_VERSION)
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
