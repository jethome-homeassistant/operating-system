#!/usr/bin/python3
# SPDX-License-Identifier: Apache-2.0
"""jethub-oled - status screens and a joystick menu on the SSD1306 OLED of
JetHub J310.

Draws through the ssd1307fb framebuffer: 128x64, 1 bpp, 16 bytes per row,
leftmost pixel in bit 0, which is Pillow's "1;R" raw packing. A write() to
the fb device pushes the whole frame to the panel synchronously.

Joystick (gpio-keys): left/right switch between Resources, Network and Clock;
center opens the menu (Network details, Reboot); back goes one level up; home
returns to Resources.

The house on Resources is the state of Home Assistant Core, asked the way
Supervisor asks it: GET /api/core/state over the Unix socket Core opens for
Supervisor, polled in a background thread.
"""

import argparse
import fcntl
import glob
import http.client
import json
import math
import os
import re
import select
import signal
import socket
import struct
import subprocess
import sys
import threading
import time

from PIL import Image, ImageDraw, ImageFont

W, H = 128, 64
STRIDE = W // 8

FONT_DIR = "/usr/share/fonts/dejavu"

# linux/input-event-codes.h
EV_KEY = 1
KEY_ENTER, KEY_HOME, KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_BACK = \
    28, 102, 103, 105, 106, 108, 158
# struct input_event of a 64-bit kernel: struct timeval, type, code, value
INPUT_EVENT = struct.Struct("qqHHi")
EVIOCGRAB = 0x40044590

HOLD = 3.0          # seconds the center key is held on Reboot
ROLLBACK = 0.3      # seconds the reboot ring takes to empty after a release
FRAME = 0.1         # frame period while the reboot ring moves
SPIN_FRAME = 0.25   # frame period of the Home Assistant spinner
ROW_KEY_SIZE = 12    # key/value rows of the details screens
ROW_VALUE_SIZE = 13  # a MAC fits at this size only without a key beside it
IP_VALUE_SIZE = 14   # the address is what these screens are opened for

# Home Assistant Core. Supervisor starts Core with SUPERVISOR_CORE_API_SOCKET
# on a bind mount of the host's /run/supervisor, and keeps its settings in
# /mnt/data/supervisor on the host.
HA_SOCKET = "/run/supervisor/core.sock"
HA_CONFIG = "/mnt/data/supervisor/homeassistant.json"
HA_HOST = "172.30.32.1"      # hassio network gateway; Core runs in the host network
HA_TIMEOUT = 5
HA_POLL_READY = 10
HA_POLL_BUSY = 3
HA_READY_MISSES = 2          # failed polls in a row before leaving "ready"
HA_DOWN_GRACE = 120          # unreachable this long is an error (a restart is shorter)
HA_BOOT_GRACE = 600          # system uptime during which unreachable is still starting
HA_START_LIMIT = 20 * 60     # Core bootstrap times out well before this
HA_INSTALL_LIMIT = 30 * 60   # landingpage: Core never got downloaded

PAGES = ("resources", "network", "clock")
MENU = ("Network", "Reboot")
NET_MENU = ("Ethernet", "Wi-Fi")
TARGET = {"Network": "netmenu", "Reboot": "reboot",
          "Ethernet": "ethernet", "Wi-Fi": "wifi"}
PARENT = {"menu": "page", "netmenu": "menu", "ethernet": "netmenu",
          "wifi": "netmenu", "reboot": "menu"}

THERM = ["..#..", ".#.#.", ".#.#.", ".#.#.", ".###.", "#####", "#####", ".###."]
ETH = [".#######.", ".#.....#.", "##.#.#.##", "#.......#", "#.#.#.#.#",
       "#.......#", "#########"]
HOUSE = ["......#......", ".....#.#.....", "....#...#....", "...#.....#...",
         "..#.......#..", ".#.........#.", "#...........#", ".#.........#.",
         ".#.........#.", ".#.........#.", ".#.........#.", ".###########."]
HOUSE_SOLID = ["......#......", ".....###.....", "....#####....", "...#######...",
               "..#########..", ".###########.", "#############", ".###########.",
               ".###########.", ".###########.", ".###########.", ".###########."]
CROSS = ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"]


def sysfs_read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


# --- panel and keys -------------------------------------------------------

def unbind_fbcon():
    """fbcon renders the VT, and with it ha-cli@tty1, onto the same panel.
    Hand the VTs back to the dummy console so nothing else draws there."""
    for name in glob.glob("/sys/class/vtconsole/vtcon*/name"):
        if "frame buffer" not in (sysfs_read(name) or ""):
            continue
        try:
            with open(os.path.join(os.path.dirname(name), "bind"), "w") as f:
                f.write("0")
        except OSError as e:
            print(f"jethub-oled: cannot unbind fbcon: {e}", file=sys.stderr)


def find_panel():
    """The framebuffer whose name ssd1307fb set to "Solomon SSD1307"."""
    for name in sorted(glob.glob("/sys/class/graphics/fb*/name")):
        if "SSD1307" in (sysfs_read(name) or ""):
            return os.path.dirname(name)
    return None


def open_panel(dev):
    sysdir = f"/sys/class/graphics/{os.path.basename(dev)}" if dev else find_panel()
    if not sysdir or not os.path.isdir(sysdir):
        sys.exit(f"jethub-oled: no SSD1307 framebuffer{' at ' + dev if dev else ''}")
    geometry = tuple(sysfs_read(f"{sysdir}/{attr}")
                     for attr in ("virtual_size", "bits_per_pixel", "stride"))
    if geometry != (f"{W},{H}", "1", str(STRIDE)):
        sys.exit(f"jethub-oled: expected a {W}x{H} 1bpp panel, got {geometry}")
    return os.open(dev or f"/dev/{os.path.basename(sysdir)}", os.O_WRONLY)


def has_keys(sysdir, codes):
    """Whether an input device reports all these key codes. The sysfs bitmap
    is a list of hex longs, most significant first."""
    bits = 0
    for word in (sysfs_read(f"{sysdir}/device/capabilities/key") or "0").split():
        bits = (bits << (8 * struct.calcsize("l"))) | int(word, 16)
    return all(bits >> c & 1 for c in codes)


def open_keys(dev):
    """The joystick, grabbed so its Enter and arrows do not also reach the
    console on tty1. gpio-keys by name, else any device with the keys."""
    if not dev:
        found = [s for s in sorted(glob.glob("/sys/class/input/event*"))
                 if has_keys(s, (KEY_ENTER, KEY_BACK, KEY_LEFT, KEY_RIGHT))]
        found.sort(key=lambda s: sysfs_read(f"{s}/device/name") != "gpio-keys")
        if not found:
            print("jethub-oled: no joystick found, running without keys",
                  file=sys.stderr)
            return None
        dev = f"/dev/input/{os.path.basename(found[0])}"
    fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
    try:
        fcntl.ioctl(fd, EVIOCGRAB, 1)
    except OSError as e:
        print(f"jethub-oled: cannot grab {dev}: {e}", file=sys.stderr)
    return fd


def read_keys(fd):
    """(code, value) of the pending key events; value 1 press, 0 release,
    2 autorepeat."""
    try:
        data = os.read(fd, INPUT_EVENT.size * 32)
    except BlockingIOError:
        return []
    data = data[:len(data) - len(data) % INPUT_EVENT.size]
    return [(code, value) for _, _, type_, code, value in INPUT_EVENT.iter_unpack(data)
            if type_ == EV_KEY]


# --- what is shown ---------------------------------------------------------

def cpu_times():
    # user nice system idle iowait irq softirq steal; guest time is already
    # counted inside user and nice.
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:9]]
    return v[3] + v[4], sum(v)


def mem_kb():
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            key, value = line.split(":", 1)
            info[key] = int(value.split()[0])
    return info["MemTotal"], info["MemAvailable"]


def thermal_zone():
    """temp of the SoC zone from the DT, else of the first zone there is."""
    zones = sorted(glob.glob("/sys/class/thermal/thermal_zone*"))
    for zone in zones:
        if sysfs_read(f"{zone}/type") == "soc_thermal":
            return f"{zone}/temp"
    return f"{zones[0]}/temp" if zones else None


def system_uptime():
    with open("/proc/uptime") as f:
        return float(f.read().split()[0])


class Stats:
    def __init__(self):
        self._cpu = cpu_times()
        self._thermal = thermal_zone()
        self.cpu = 0
        self.sample()

    def sample(self):
        idle, total = cpu_times()
        d_idle, d_total = idle - self._cpu[0], total - self._cpu[1]
        self._cpu = (idle, total)
        if d_total:
            self.cpu = 100 * (d_total - d_idle) // d_total
        total_kb, avail_kb = mem_kb()
        self.mem = 100 * (total_kb - avail_kb) // total_kb
        temp = sysfs_read(self._thermal) if self._thermal else None
        self.temp = int(temp) // 1000 if temp and temp.lstrip("-").isdigit() else None
        self.uptime = system_uptime()


def uptime_text(seconds):
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def default_iface():
    """The interface of the default route with the lowest metric."""
    best = None
    try:
        with open("/proc/net/route") as f:
            next(f)
            for line in f:
                iface, dest, _, flags, _, _, metric = line.split()[:7]
                if dest == "00000000" and int(flags, 16) & 1:  # RTF_UP
                    if best is None or int(metric) < best[0]:
                        best = (int(metric), iface)
    except (OSError, ValueError, StopIteration):
        pass
    return best[1] if best else None


def ipv4():
    """The source address of the default route: the one Home Assistant is
    reached at, not a Docker bridge. connect() on a UDP socket only does the
    route lookup; nothing is sent to the TEST-NET address."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
        except OSError:
            return None


class Traffic:
    """Bytes per second of an interface, from one sample to the next."""

    def __init__(self):
        self._last = {}

    def rate(self, iface, now):
        counters = tuple(
            int(sysfs_read(f"/sys/class/net/{iface}/statistics/{name}", "0") or 0)
            for name in ("rx_bytes", "tx_bytes"))
        before = self._last.get(iface)
        self._last[iface] = (now, counters)
        if not before or now <= before[0]:
            return None
        seconds = now - before[0]
        return tuple(max(0, new - old) / seconds for new, old in zip(counters, before[1]))


def human_rate(value):
    for unit in ("", "K", "M", "G"):
        if value < 1000:
            break
        value /= 1024
    if unit == "":
        return f"{round(value)}"
    return f"{value:.1f}{unit}" if value < 10 else f"{round(value)}{unit}"


def link_speed(iface):
    speed = sysfs_read(f"/sys/class/net/{iface}/speed", "")
    mbit = int(speed) if speed.lstrip("-").isdigit() else -1
    if mbit >= 1000:
        return f"{mbit // 1000} Gbit"
    return f"{mbit} Mbit" if mbit > 0 else ""


def nm_fields(line):
    """A line of nmcli -t with several fields; ':' in a value is escaped."""
    return [f.replace("\\:", ":").replace("\\\\", "\\")
            for f in re.split(r"(?<!\\):", line)]


class Network:
    """Details from NetworkManager, cached: nmcli is too slow for every frame."""
    TTL = 5

    def __init__(self):
        self._cache = {}

    def _nmcli(self, *args):
        now = time.monotonic()
        hit = self._cache.get(args)
        if hit and now - hit[0] < self.TTL:
            return hit[1]
        try:
            out = subprocess.run(["nmcli", "-t", *args], capture_output=True,
                                 text=True, timeout=2).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        self._cache[args] = (now, out)
        return out

    def devices(self):
        """{"ethernet": (device, connected), "wifi": ...}, first of each type."""
        found = {}
        for line in self._nmcli("-f", "DEVICE,TYPE,STATE", "device").splitlines():
            f = nm_fields(line)
            if len(f) == 3 and f[1] in ("ethernet", "wifi") and f[1] not in found:
                found[f[1]] = (f[0], f[2] == "connected")
        return found

    def details(self, dev):
        """First address (without the prefix), gateway, DNS server and MAC."""
        info = {}
        out = self._nmcli("-f", "GENERAL.HWADDR,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                          "device", "show", dev)
        for line in out.splitlines():
            key, _, value = line.partition(":")
            key = key.split("[")[0]
            if value and value != "--" and key not in info:
                info[key] = value.split("/")[0] if key == "IP4.ADDRESS" else value
        return info

    def ip_method(self, dev):
        """DHCP or Static, as the profile of the device says."""
        conn = ""
        for line in self._nmcli("-f", "GENERAL.CONNECTION", "device", "show", dev).splitlines():
            key, _, value = line.partition(":")
            if key == "GENERAL.CONNECTION":
                conn = value
        if not conn:
            return None
        for line in self._nmcli("-f", "ipv4.method", "connection", "show", conn).splitlines():
            key, _, value = line.partition(":")
            if key == "ipv4.method":
                return {"auto": "DHCP", "manual": "Static"}.get(value)
        return None

    def online(self):
        """Whether NetworkManager sees a way out to the internet. It checks
        on its own schedule and on every link change, so this is just a read.
        "unknown" means the check is off, which is not an outage."""
        state = self._nmcli("-f", "CONNECTIVITY", "general").strip()
        return state in ("full", "unknown", "")

    def wifi(self, dev):
        """SSID and signal in percent of the network the device is on."""
        out = self._nmcli("-f", "IN-USE,SSID,SIGNAL", "device", "wifi", "list",
                          "ifname", dev, "--rescan", "no")
        for line in out.splitlines():
            f = nm_fields(line)
            if len(f) == 3 and f[0] == "*":
                return f[1], int(f[2]) if f[2].isdigit() else None
        return None, None


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, timeout):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def core_config():
    """Supervisor's record of Core: version, port, ssl."""
    try:
        with open(HA_CONFIG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def core_state():
    """Core's own view of its state, or None if the socket does not answer.
    Core authenticates requests on this socket as the Supervisor user, so no
    token is involved; only this read-only endpoint is used."""
    conn = UnixHTTPConnection(HA_SOCKET, HA_TIMEOUT)
    try:
        conn.request("GET", "/api/core/state")
        resp = conn.getresponse()
        return json.load(resp) if resp.status == 200 else None
    except (OSError, ValueError, http.client.HTTPException):
        return None
    finally:
        conn.close()


def core_port_open(config):
    try:
        port = int(config.get("port", 8123))
        with socket.create_connection((HA_HOST, port), timeout=HA_TIMEOUT):
            return True
    except (OSError, ValueError):
        return False


class HomeAssistant(threading.Thread):
    """starting / ready / error for the badge on Resources."""
    STARTING, READY, ERROR = "starting", "ready", "error"

    def __init__(self):
        super().__init__(name="ha-status", daemon=True)
        self.state = self.STARTING
        self._since = {}   # condition -> when it was first seen in a row
        self._misses = 0

    def run(self):
        while True:
            try:
                self.state = self.poll(time.monotonic())
            except Exception as e:  # keep polling whatever one probe hit
                print(f"jethub-oled: Home Assistant status: {e}", file=sys.stderr)
            time.sleep(HA_POLL_READY if self.state == self.READY else HA_POLL_BUSY)

    def poll(self, now):
        state = self._probe(now)
        if state == self.READY:
            self._misses = 0
            self._since.clear()
        elif self.state == self.READY:
            # One slow answer on a busy board is not an outage.
            self._misses += 1
            if self._misses < HA_READY_MISSES:
                return self.READY
        return state

    def _for(self, condition, now, limit, uptime_grace=False):
        """STARTING while condition has lasted less than limit, then ERROR."""
        for other in list(self._since):
            if other != condition:
                del self._since[other]
        since = self._since.setdefault(condition, now)
        if now - since < limit or (uptime_grace and system_uptime() < HA_BOOT_GRACE):
            return self.STARTING
        return self.ERROR

    def _probe(self, now):
        # Without an address nobody can reach Home Assistant, however happy
        # the container is, so the badge calls that broken.
        if ipv4() is None:
            self._since.clear()
            return self.ERROR
        config = core_config()
        if config.get("version") == "landingpage":
            return self._for("install", now, HA_INSTALL_LIMIT)
        data = core_state()
        if data is not None:
            recorder = data.get("recorder_state") or {}
            if data.get("state") == "RUNNING":
                return self.READY
            if recorder.get("migration_in_progress") and not recorder.get("migration_is_live"):
                # An offline database migration can take hours; Core is busy, not broken.
                self._since.clear()
                return self.STARTING
            if data.get("state") in ("STARTING", "NOT_RUNNING"):
                return self._for("starting", now, HA_START_LIMIT)
            # STOPPING, FINAL_WRITE, STOPPED: going down, perhaps to restart
        elif core_port_open(config):
            # Listening, but the socket comes up only with the hassio integration.
            return self._for("starting", now, HA_START_LIMIT)
        return self._for("down", now, HA_DOWN_GRACE, uptime_grace=True)


# --- drawing ---------------------------------------------------------------

class Fonts:
    def __init__(self, directory):
        self.dir = directory
        self._faces = {}
        self.label = self.get("DejaVuSansCondensed.ttf", 11)
        self.small = self.get("DejaVuSansCondensed.ttf", 12)
        self.menu = self.get("DejaVuSansCondensed.ttf", 12)
        self.value = self.get("DejaVuSansCondensed-Bold.ttf", 12)
        self.hint = self.get("DejaVuSansCondensed-Bold.ttf", 12)
        self.status = self.get("DejaVuSansCondensed-Bold.ttf", 12)
        self.ring = self.get("DejaVuSansCondensed-Bold.ttf", 15)
        self.header = self.get("DejaVuSans-Bold.ttf", 11)
        self.temp = self.get("DejaVuSans-Bold.ttf", 14)
        self.clock = self.get("DejaVuSansMono-Bold.ttf", 32)

    def get(self, name, size):
        key = (name, size)
        if key not in self._faces:
            self._faces[key] = ImageFont.truetype(os.path.join(self.dir, name), size)
        return self._faces[key]

    def fit(self, draw, s, width, name, sizes):
        """The largest of sizes at which s is at most width pixels wide."""
        for size in sizes:
            face = self.get(name, size)
            if draw.textlength(s, font=face) <= width:
                break
        return face


def text(draw, x, baseline, s, face, anchor="ls", fill=1):
    draw.text((x, baseline), s, font=face, fill=fill, anchor=anchor)


def clip(draw, s, face, width):
    """Cut a value to the characters that fit, the last one an ellipsis."""
    if draw.textlength(s, font=face) <= width:
        return s
    fits = s
    while fits and draw.textlength(fits, font=face) > width:
        fits = fits[:-1]
    return fits[:-1] + "…" if fits else ""


def icon(im, x, y, rows):
    px = im.load()
    for j, row in enumerate(rows):
        for i, c in enumerate(row):
            if c == "#":
                px[x + i, y + j] = 1


def bars(draw, x, bottom, level, fill=1):
    """Signal strength: four bars, level of them solid."""
    for i in range(4):
        box = (x + i * 5, bottom - 3 - i * 2, x + i * 5 + 3, bottom)
        if i < level:
            draw.rectangle(box, fill=fill)
        else:
            draw.rectangle(box, outline=fill)


def dotted(draw, y, x0=0, x1=W - 1):
    for x in range(x0, x1 + 1, 2):
        draw.point((x, y), 1)


def point_on(cx, cy, r, degrees):
    """0 degrees at 12 o'clock, clockwise."""
    t = math.radians(degrees - 90)
    return round(cx + r * math.cos(t)), round(cy + r * math.sin(t))


def track(draw, cx, cy, r, step=12):
    for a in range(0, 360, step):
        draw.point(point_on(cx, cy, r, a), 1)


def arc(draw, cx, cy, r, pct, width):
    if pct > 0:
        draw.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * min(pct, 100) / 100,
                 fill=1, width=width)


def ha_badge(im, draw, cx, cy, r, state, now):
    """A house in a ring: a comet going round while starting, solid when
    ready, a cross in the house on error."""
    hx, hy = cx - len(HOUSE[0]) // 2, cy - len(HOUSE) // 2
    if state == HomeAssistant.READY:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=1, width=2)
        icon(im, hx, hy, HOUSE_SOLID)
        return
    track(draw, cx, cy, r, 24)
    icon(im, hx, hy, HOUSE)
    if state == HomeAssistant.ERROR:
        icon(im, hx + 4, hy + 6, CROSS)
        return
    head = int(now / SPIN_FRAME) % 8 * 45
    for a in range(0, 120, 5):
        x, y = point_on(cx, cy, r, head + a)
        k = 1 if a > 40 else 0
        draw.rectangle((x - k, y - k, x, y), fill=1)


def header(draw, fonts, title, right=None):
    draw.rectangle((0, 0, W - 1, 11), fill=1)
    text(draw, 4, 9, title, fonts.header, fill=0)
    if right:
        text(draw, 123, 9, right, fonts.label, "rs", fill=0)


def centered(draw, fonts, s):
    text(draw, W // 2, 42, s, fonts.small, "ms")


class UI:
    """Which screen is up, what the keys do to it, and how it looks."""

    def __init__(self, fonts, stats, net, ha):
        self.f, self.stats, self.net, self.ha = fonts, stats, net, ha
        self.traffic = Traffic()
        self.screen = "page"
        self.page = 0
        self.sel = {"menu": 0, "netmenu": 0}
        self.hold_start = None   # center pressed on Reboot at
        self.rollback = None     # (ring percent, released at)
        self.rebooting = False

    # keys and time

    def _go(self, screen):
        if PARENT.get(screen) == self.screen and screen in self.sel:
            self.sel[screen] = 0
        self.screen = screen
        self.hold_start = self.rollback = None

    def key(self, code, value, now):
        if value == 2 or self.rebooting:
            return
        if value == 0:
            if code == KEY_ENTER and self.hold_start is not None:
                self.rollback = (self.ring_pct(now), now)
                self.hold_start = None
            return
        if code == KEY_HOME:
            self._go("page")
            self.page = 0
            return
        s = self.screen
        if s == "page":
            if code in (KEY_LEFT, KEY_RIGHT):
                self.page = (self.page + (1 if code == KEY_RIGHT else -1)) % len(PAGES)
            elif code == KEY_ENTER:
                self._go("menu")
        elif s in ("menu", "netmenu"):
            items = MENU if s == "menu" else NET_MENU
            if code in (KEY_UP, KEY_DOWN):
                self.sel[s] = (self.sel[s] + (1 if code == KEY_DOWN else -1)) % len(items)
            elif code in (KEY_ENTER, KEY_RIGHT):
                self._go(TARGET[items[self.sel[s]]])
            elif code in (KEY_BACK, KEY_LEFT):
                self._go(PARENT[s])
        elif s == "reboot":
            # Only a press made on this screen counts: the one that opened it
            # from the menu is released here and ignored.
            if code == KEY_ENTER:
                self.hold_start, self.rollback = now, None
            elif code in (KEY_BACK, KEY_LEFT):
                self._go(PARENT[s])
        elif code in (KEY_BACK, KEY_LEFT):
            self._go(PARENT[s])

    def tick(self, now):
        """Advance timers; True once, when the reboot hold completes."""
        if self.hold_start is not None and now - self.hold_start >= HOLD:
            self.hold_start = None
            self.rebooting = True
            return True
        if self.rollback and now - self.rollback[1] >= ROLLBACK:
            self.rollback = None
        return False

    def frame_period(self):
        """How soon the next frame is due for an animation, or None."""
        if self.hold_start is not None or self.rollback is not None:
            return FRAME
        if (self.screen, PAGES[self.page]) == ("page", "resources") \
                and self.ha.state == HomeAssistant.STARTING:
            return SPIN_FRAME
        return None

    def ring_pct(self, now):
        if self.rebooting:
            return 100
        if self.hold_start is not None:
            return min(100, 100 * (now - self.hold_start) / HOLD)
        if self.rollback:
            pct, released = self.rollback
            return max(0, pct * (1 - (now - released) / ROLLBACK))
        return 0

    # screens

    def render(self, now):
        im = Image.new("1", (W, H))
        d = ImageDraw.Draw(im)
        d.fontmode = "1"  # no antialiasing on a 1-bit panel
        s = self.screen
        if s == "page":
            getattr(self, "draw_" + PAGES[self.page])(im, d, now)
        elif s == "menu":
            self.draw_menu(d, "Menu", MENU, self.sel[s])
        elif s == "netmenu":
            devs = self.net.devices()
            self.draw_menu(d, "Network", NET_MENU, self.sel[s],
                           [devs.get(k, (None, False))[1] for k in ("ethernet", "wifi")])
            if not self.net.online():
                text(d, W // 2, 62, "No internet", self.f.label, "ms")
        elif s == "ethernet":
            self.draw_ethernet(d, now)
        elif s == "wifi":
            self.draw_wifi(d)
        elif s == "reboot":
            self.draw_reboot(d, now)
        return im

    def draw_resources(self, im, d, now):
        f, st = self.f, self.stats
        for cx, pct, label in ((22, st.cpu, "CPU"), (66, st.mem, "RAM")):
            track(d, cx, 26, 20)
            arc(d, cx, 26, 21, pct, 4)
            value = str(pct)
            face = f.fit(d, value, 28, "DejaVuSansCondensed-Bold.ttf", range(17, 11, -1))
            text(d, cx, 31, value, face, "ms")
            text(d, cx, 63, label, f.small, "ms")
        ha_badge(im, d, 109, 11, 10, self.ha.state, now)
        dotted(d, 24, 90)
        icon(im, 91, 29, THERM)
        text(d, 127, 41, "--°" if st.temp is None else f"{st.temp}°", f.temp, "rs")
        dotted(d, 46, 90)
        up = f"up {uptime_text(st.uptime)}"
        text(d, 127, 61, up, f.fit(d, up, 37, "DejaVuSansCondensed-Bold.ttf", range(12, 7, -1)), "rs")

    def draw_network(self, im, d, now):
        f = self.f
        iface = default_iface()
        ip = ipv4() if iface else None
        if iface and os.path.isdir(f"/sys/class/net/{iface}/wireless"):
            bars(d, 0, 10, 4)
            text(d, 23, 10, "Wi-Fi", f.label)
        elif iface:
            icon(im, 0, 3, ETH)
            text(d, 12, 10, f"Ethernet  {link_speed(iface)}".rstrip(), f.label)
        big = ip or "No network"
        face = f.fit(d, big, W - 2, "DejaVuSansCondensed-Bold.ttf", range(18, 8, -1))
        text(d, W // 2, 36, big, face, "ms")
        dotted(d, 44, 8, 119)
        if ip and not self.net.online():
            text(d, W // 2, 59, "No internet", f.value, "ms")
        else:
            host = socket.gethostname() + ".local"
            face = f.fit(d, host, W - 2, "DejaVuSansCondensed.ttf", range(14, 7, -1))
            text(d, W // 2, 59, host, face, "ms")

    def draw_clock(self, im, d, now):
        t = time.localtime()
        text(d, W // 2, 40, time.strftime("%H:%M", t), self.f.clock, "ms")
        dotted(d, 47, 20, 107)
        date = f"{time.strftime('%a', t)}, {t.tm_mday} {time.strftime('%b', t)}"
        text(d, W // 2, 60, date, self.f.small, "ms")

    def draw_menu(self, d, title, items, sel, connected=None):
        header(d, self.f, title, f"{sel + 1}/{len(items)}")
        for i, name in enumerate(items):
            base = 30 + i * 18
            fill = 1
            if i == sel:
                d.rounded_rectangle((0, base - 12, W - 1, base + 3), radius=3, fill=1)
                fill = 0
            text(d, 6, base, ("›  " if i == sel else "   ") + name, self.f.menu, fill=fill)
            if connected is not None:
                dot = (118 - 3, base - 7, 118 + 3, base - 1)
                if connected[i]:
                    d.ellipse(dot, fill=fill)
                else:
                    d.ellipse(dot, outline=fill)

    def row_width(self, d, key):
        """What is left for a value once its key is drawn."""
        return W - 4 - d.textlength(key, font=self.f.get("DejaVuSansCondensed-Bold.ttf",
                                                         ROW_KEY_SIZE)) - 4

    def draw_rows(self, d, rows, top=26, step=14):
        """Key in bold on the left, value on the right as large as it fits.
        The value is upright: it is narrower than bold, so it can be larger.
        A row may name its own value size as a third field."""
        f = self.f
        key_face = f.get("DejaVuSansCondensed-Bold.ttf", ROW_KEY_SIZE)
        # One fixed size on every details screen, so Ethernet and Wi-Fi look
        # alike. It is the size at which a MAC still fits next to its key;
        # anything longer, such as a long SSID, is cut with an ellipsis.
        for i, row in enumerate(rows):
            key, value = row[0], row[1]
            size = row[2] if len(row) > 2 else ROW_VALUE_SIZE
            base = top + i * step
            text(d, 2, base, key, key_face)
            text(d, W - 1, base, value, f.get("DejaVuSansCondensed.ttf", size), "rs")

    def draw_ethernet(self, d, now):
        dev, up = self.net.devices().get("ethernet", (None, False))
        header(d, self.f, "Ethernet", self.net.ip_method(dev) if up else None)
        if not dev:
            return centered(d, self.f, "No Ethernet")
        face = self.f.get("DejaVuSansCondensed.ttf", ROW_VALUE_SIZE)
        text(d, W // 2, 34, self.net.details(dev).get("IP4.ADDRESS", "--"),
             self.f.get("DejaVuSansCondensed.ttf", IP_VALUE_SIZE), "ms")
        rate = self.traffic.rate(dev, now)
        # Until there are two samples there is nothing to divide, so say so
        # rather than claim an idle link.
        line = ("\u2193 --  \u2191 --" if rate is None else
                f"\u2193 {human_rate(rate[0])}  \u2191 {human_rate(rate[1])}")
        text(d, W // 2, 56, line, face, "ms")

    def draw_wifi(self, d):
        dev, up = self.net.devices().get("wifi", (None, False))
        header(d, self.f, "Wi-Fi")
        if not dev:
            return centered(d, self.f, "No Wi-Fi")
        if not up:
            return centered(d, self.f, "Not connected")
        ssid, signal_pct = self.net.wifi(dev)
        info = self.net.details(dev)
        if signal_pct is not None:
            bars(d, 104, 9, min(4, (signal_pct + 10) // 20), fill=0)
        ssid = clip(d, ssid or "--", self.f.get("DejaVuSansCondensed.ttf", ROW_VALUE_SIZE),
                    self.row_width(d, "SSID"))
        self.draw_rows(d, [("SSID", ssid),
                           ("IP", info.get("IP4.ADDRESS", "--"), IP_VALUE_SIZE),
                           ("Signal", "--" if signal_pct is None else f"{signal_pct}%")],
                       top=28, step=17)

    def draw_reboot(self, d, now):
        f = self.f
        header(d, f, "Reboot")
        cx, cy = 18, 38
        if not self.rebooting:
            track(d, cx, cy, 14, 15)
        arc(d, cx, cy, 15, self.ring_pct(now), 4)
        d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=1)
        if self.rebooting:
            text(d, 40, 42, "Rebooting...", f.status)
        else:
            text(d, 40, 36, "Hold center", f.small)
            text(d, 40, 52, "for 3 s", f.hint)


# --- main loop -------------------------------------------------------------

def dump(frame):
    px = frame.load()
    for y in range(H):
        print("".join("#" if px[x, y] else "." for x in range(W)))
    print(flush=True)


def reboot():
    # In its own session, so systemd does not wait for it as part of this
    # service while it is busy running the shutdown transaction.
    try:
        subprocess.Popen(["systemctl", "reboot"], start_new_session=True)
    except OSError as e:
        print(f"jethub-oled: cannot reboot: {e}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description="Status screens and a joystick menu "
                                            "on the JetHub OLED")
    p.add_argument("-d", metavar="/dev/fbN",
                   help="framebuffer device (default: the one named SSD1307)")
    p.add_argument("-k", metavar="/dev/input/eventN",
                   help="joystick device (default: gpio-keys)")
    p.add_argument("-f", metavar="DIR", default=FONT_DIR,
                   help=f"DejaVu font directory (default {FONT_DIR})")
    p.add_argument("-t", action="store_true",
                   help="print frames as text instead of drawing them")
    args = p.parse_args()

    try:
        fonts = Fonts(args.f)
    except OSError as e:
        sys.exit(f"jethub-oled: cannot load fonts from {args.f}: {e}")

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    fd = keys = None
    if not args.t:
        unbind_fbcon()
        fd = open_panel(args.d)
        keys = open_keys(args.k)

    ha = HomeAssistant()
    ha.start()
    ui = UI(fonts, Stats(), Network(), ha)
    shown = None
    next_sample = time.monotonic() + 1
    try:
        while True:
            now = time.monotonic()
            if now >= next_sample:
                ui.stats.sample()
                next_sample = now + 1
            if ui.tick(now):
                reboot()

            data = ui.render(now).tobytes("raw", "1;R")
            # Unchanged frames are skipped: each write is ~1 KiB of i2c traffic.
            if data != shown:
                if args.t:
                    dump(Image.frombytes("1", (W, H), data, "raw", "1;R"))
                else:
                    try:
                        os.pwrite(fd, data, 0)
                    except OSError as e:
                        sys.exit(f"jethub-oled: write to panel failed: {e}")
                shown = data

            timeout = max(0, next_sample - time.monotonic())
            period = ui.frame_period()
            if period is not None:
                timeout = min(timeout, period - time.monotonic() % period)
            if keys is None:
                time.sleep(timeout)
            elif select.select([keys], [], [], timeout)[0]:
                now = time.monotonic()
                for code, value in read_keys(keys):
                    ui.key(code, value, now)
    except KeyboardInterrupt:
        pass
    finally:
        if fd is not None:
            # Leave the panel dark rather than frozen on stale numbers; after
            # a reboot request keep "Rebooting..." up instead.
            if not ui.rebooting:
                try:
                    os.pwrite(fd, bytes(STRIDE * H), 0)
                except OSError:
                    pass
            os.close(fd)


if __name__ == "__main__":
    main()
