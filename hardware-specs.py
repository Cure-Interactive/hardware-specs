#!/usr/bin/env python3
# =============================================================================
# [Python Script] [CustomTkinter GUI] [Hardware Specs]
# =============================================================================
"""
Hardware specs desktop app.

Shows a concise set of machine specs commonly used to assess workstation
capability:
- Device manufacturer and model
- CPU model, cores, threads, max clock
- Installed memory
- GPU model(s) and memory
- Fixed storage devices and capacities
- Display count and resolutions

The app is Windows-oriented and uses PowerShell/CIM for data collection.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont


APP_TITLE = "Hardware Specs - Cure Interactive"
APP_USER_MODEL_ID = "CureInteractive.HardwareSpecs"

PATH_DIR_SCRIPT = os.path.abspath(os.path.dirname(__file__))
PATH_CONFIG_JSON = os.path.join(PATH_DIR_SCRIPT, "config.json")

DEFAULT_CONFIG = {
  "window": {
    "width": 1120,
    "height": 760,
  },
  "appearance_mode": "System",
  "color_theme": "blue",
}

CARD_FG_COLOR = ("#f2f2f2", "#353535")
GROUP_CARD_FG_COLOR = ("#e5e5e5", "#262626")
ITEM_CARD_FG_COLOR = ("#dddddd", "#202020")
EXPORT_BG_COLOR = "#2b2b2b"
EXPORT_CARD_COLOR = "#353535"
EXPORT_GROUP_COLOR = "#262626"
EXPORT_TEXT_PRIMARY = "#f4f4f4"
EXPORT_TEXT_MUTED = "#d8d8d8"

EXPORT_PADDING = 10
EXPORT_CARD_GAP = 10
EXPORT_INNER_GAP = 6
EXPORT_CANVAS_WIDTH = 1600
EXPORT_COLUMN_GAP = 10
EXPORT_TITLE_SIZE = 18
EXPORT_LABEL_SIZE = 11
EXPORT_VALUE_SIZE = 13


def build_qa_sample_data() -> dict:
  return {
    "computer": {
      "Manufacturer": "ASUS",
      "Model": "System Product Name",
      "TotalPhysicalMemory": 68585259008,
    },
    "cpu": {
      "Name": "Intel(R) Core(TM) i9-10900K CPU @ 3.70GHz",
      "NumberOfCores": 10,
      "NumberOfLogicalProcessors": 20,
      "MaxClockSpeed": 3700,
    },
    "gpu": [
      {
        "Name": "Intel(R) UHD Graphics 630",
        "AdapterRAM": 1073741824,
      },
      {
        "Name": "NVIDIA GeForce RTX 3090 Ti",
        "AdapterRAM": 4294967296,
      },
    ],
    "storage": [
      {
        "FriendlyName": "Seagate FireCuda 530 ZP1000GM30013",
        "MediaType": "SSD",
        "BusType": "NVMe",
        "Size": 1000727379968,
      },
      {
        "FriendlyName": "Samsung SSD 970 EVO Plus 1TB",
        "MediaType": "SSD",
        "BusType": "NVMe",
        "Size": 1000204886016,
      },
      {
        "FriendlyName": "Samsung SSD 870 EVO 4TB",
        "MediaType": "SSD",
        "BusType": "SATA",
        "Size": 4000787030016,
      },
      {
        "FriendlyName": "Samsung SSD 870 EVO 4TB",
        "MediaType": "SSD",
        "BusType": "SATA",
        "Size": 4000787030016,
      },
      {
        "FriendlyName": "ATA ST500DM002-1BD14",
        "MediaType": "HDD",
        "BusType": "SAS",
        "Size": 500107862016,
      },
    ],
    "displays": [
      {"Width": 1344, "Height": 840, "Primary": False},
      {"Width": 1344, "Height": 840, "Primary": False},
      {"Width": 1536, "Height": 864, "Primary": True},
      {"Width": 1280, "Height": 720, "Primary": False},
      {"Width": 1536, "Height": 864, "Primary": False},
    ],
  }


def _read_json(path: str) -> dict | None:
  try:
    if not os.path.isfile(path):
      return None
    with open(path, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return None


def _write_json_atomic(path: str, data: dict) -> None:
  tmp = path + ".tmp"
  with open(tmp, "w", encoding="utf-8", newline="\n") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
  os.replace(tmp, path)


def load_or_create_config(path: str) -> dict:
  cfg = _read_json(path)
  if isinstance(cfg, dict):
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update(cfg)
    if isinstance(cfg.get("window"), dict):
      merged["window"].update(cfg["window"])
    return merged

  _write_json_atomic(path, DEFAULT_CONFIG)
  return json.loads(json.dumps(DEFAULT_CONFIG))


def set_windows_app_user_model_id(app_id: str) -> None:
  try:
    if os.name != "nt":
      return
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
  except Exception:
    return


def set_window_icon(root, ico_path: str, png_path: str) -> None:
  ico_abs = os.path.abspath(ico_path) if ico_path else ""
  png_abs = os.path.abspath(png_path) if png_path else ""

  try:
    if ico_abs and os.path.isfile(ico_abs):
      root.iconbitmap(ico_abs)
  except Exception:
    pass

  try:
    if png_abs and os.path.isfile(png_abs):
      img = tk.PhotoImage(file=png_abs)
      root.iconphoto(True, img)
      root._iconphoto_ref = img
  except Exception:
    pass


def _bytes_to_gib_text(value: object) -> str:
  try:
    number = int(value)
  except Exception:
    return "Unknown"
  gib = number / (1024 ** 3)
  if gib >= 100:
    return f"{gib:.0f} GB"
  return f"{gib:.1f} GB"


def _mhz_to_ghz_text(value: object) -> str:
  try:
    mhz = int(value)
  except Exception:
    return "Unknown"
  return f"{mhz / 1000.0:.2f} GHz"


def _coalesce(value: object, fallback: str = "Unknown") -> str:
  text = str(value or "").strip()
  return text if text else fallback


def _normalize_items(value: object) -> list[dict]:
  if isinstance(value, list):
    return [item for item in value if isinstance(item, dict)]
  if isinstance(value, dict):
    return [value]
  return []


def _normalized_system_name(manufacturer: object, model: object) -> str:
  manufacturer_text = str(manufacturer or "").strip()
  model_text = str(model or "").strip()

  generic_models = {
    "",
    "system product name",
    "to be filled by o.e.m.",
    "to be filled by oem",
    "default string",
    "not applicable",
  }

  if model_text.lower() in generic_models:
    if manufacturer_text:
      return f"{manufacturer_text} Custom Desktop"
    return "Custom Desktop"

  if manufacturer_text and model_text and not model_text.lower().startswith(manufacturer_text.lower()):
    return f"{manufacturer_text} {model_text}"

  return model_text or manufacturer_text or "Unknown"


def _resolve_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
  candidates = []
  if os.name == "nt":
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    candidates.extend([
      os.path.join(win_dir, "Fonts", "segoeuib.ttf" if bold else "segoeui.ttf"),
      os.path.join(win_dir, "Fonts", "arialbd.ttf" if bold else "arial.ttf"),
    ])

  for path in candidates:
    if os.path.isfile(path):
      try:
        return ImageFont.truetype(path, size)
      except Exception:
        continue

  return ImageFont.load_default()


def _text_box_height(text: str, font, width: int, *, line_spacing: int = 4) -> tuple[list[str], int]:
  words = text.split()
  if not words:
    return [""], int(font.size if hasattr(font, "size") else 14) + line_spacing

  img = Image.new("RGB", (10, 10))
  draw = ImageDraw.Draw(img)
  lines: list[str] = []
  current = words[0]

  for word in words[1:]:
    candidate = f"{current} {word}"
    bbox = draw.textbbox((0, 0), candidate, font=font)
    if (bbox[2] - bbox[0]) <= width:
      current = candidate
    else:
      lines.append(current)
      current = word
  lines.append(current)

  sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
  line_height = max(1, sample_bbox[3] - sample_bbox[1])
  total_height = (line_height * len(lines)) + (line_spacing * max(0, len(lines) - 1))
  return lines, total_height


def _measure_stat_block_height(value: str, width: int) -> int:
  value_font = _resolve_font(EXPORT_VALUE_SIZE, bold=True)
  _, value_height = _text_box_height(value, value_font, width - 16)
  return 6 + 14 + 2 + value_height + 6


def _measure_item_block_height(item: dict[str, str], width: int) -> int:
  title_font = _resolve_font(12, bold=True)
  body_font = _resolve_font(12, bold=False)
  meta_font = _resolve_font(11, bold=False)

  _, title_height = _text_box_height(item.get("title", ""), title_font, width - 16)
  _, subtitle_height = _text_box_height(item.get("subtitle", ""), body_font, width - 16)

  total = 6 + title_height + 1 + subtitle_height + 4
  meta_left = item.get("meta_left", "")
  meta_right = item.get("meta_right", "")
  if meta_left or meta_right:
    meta_text = f"{meta_left} {meta_right}".strip()
    _, meta_height = _text_box_height(meta_text, meta_font, width - 16)
    total += meta_height + 6
  else:
    total += 2
  return total


def _measure_card_height(
  stats: list[tuple[str, str]],
  items: list[dict[str, str]],
  *,
  width: int,
  item_columns: int,
) -> int:
  title_height = 8 + EXPORT_TITLE_SIZE + 6
  total = title_height

  if stats:
    stat_width = (width - (EXPORT_PADDING * 2) - EXPORT_INNER_GAP) // 2
    stat_heights = [_measure_stat_block_height(value, stat_width) for _, value in stats]
    rows = [stat_heights[i:i + 2] for i in range(0, len(stat_heights), 2)]
    total += sum(max(row) for row in rows) + (EXPORT_INNER_GAP * max(0, len(rows) - 1)) + 6

  if items:
    item_width = (width - (EXPORT_PADDING * 2) - (EXPORT_INNER_GAP * (item_columns - 1))) // item_columns
    item_heights = [_measure_item_block_height(item, item_width) for item in items]
    rows = [item_heights[i:i + item_columns] for i in range(0, len(item_heights), item_columns)]
    total += sum(max(row) for row in rows) + (EXPORT_INNER_GAP * max(0, len(rows) - 1)) + 6

  return total + 8


def _draw_wrapped_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill: str, width: int) -> int:
  lines, height = _text_box_height(text, font, width)
  sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
  line_height = max(1, sample_bbox[3] - sample_bbox[1])
  x, y = xy
  for index, line in enumerate(lines):
    draw.text((x, y + index * (line_height + 4)), line, font=font, fill=fill)
  return height


def _assert_rect_within(
  outer: tuple[int, int, int, int],
  inner: tuple[int, int, int, int],
  label: str,
) -> None:
  ox1, oy1, ox2, oy2 = outer
  ix1, iy1, ix2, iy2 = inner
  if ix1 < ox1 or iy1 < oy1 or ix2 > ox2 or iy2 > oy2:
    raise RuntimeError(f"Export layout overflow in {label}.")


def export_cards_image(path: str, cards: list[dict[str, object]]) -> None:
  title_font = _resolve_font(EXPORT_TITLE_SIZE, bold=True)
  label_font = _resolve_font(EXPORT_LABEL_SIZE, bold=True)
  value_font = _resolve_font(EXPORT_VALUE_SIZE, bold=True)
  body_font = _resolve_font(12, bold=False)
  body_bold_font = _resolve_font(12, bold=True)
  meta_font = _resolve_font(11, bold=False)

  left_width = (EXPORT_CANVAS_WIDTH - (EXPORT_PADDING * 2) - EXPORT_COLUMN_GAP) // 2
  right_width = left_width

  layout: list[dict[str, object]] = []
  for index, card in enumerate(cards):
    item_columns = 4 if index == 4 else 2
    width = EXPORT_CANVAS_WIDTH - (EXPORT_PADDING * 2) if index == 4 else left_width
    height = _measure_card_height(
      list(card["stats"]),
      list(card["items"]),
      width=width,
      item_columns=item_columns,
    )
    layout.append({
      "title": str(card["title"]),
      "stats": list(card["stats"]),
      "items": list(card["items"]),
      "width": width,
      "height": height,
      "item_columns": item_columns,
    })

  row0_height = max(layout[0]["height"], layout[1]["height"])
  row1_height = max(layout[2]["height"], layout[3]["height"])
  total_height = (
    EXPORT_PADDING
    + row0_height
    + EXPORT_CARD_GAP
    + row1_height
    + EXPORT_CARD_GAP
    + layout[4]["height"]
    + EXPORT_PADDING
  )

  image = Image.new("RGB", (EXPORT_CANVAS_WIDTH, total_height), EXPORT_BG_COLOR)
  draw = ImageDraw.Draw(image)

  positions = [
    (EXPORT_PADDING, EXPORT_PADDING),
    (EXPORT_PADDING + left_width + EXPORT_COLUMN_GAP, EXPORT_PADDING),
    (EXPORT_PADDING, EXPORT_PADDING + row0_height + EXPORT_CARD_GAP),
    (EXPORT_PADDING + left_width + EXPORT_COLUMN_GAP, EXPORT_PADDING + row0_height + EXPORT_CARD_GAP),
    (EXPORT_PADDING, EXPORT_PADDING + row0_height + EXPORT_CARD_GAP + row1_height + EXPORT_CARD_GAP),
  ]

  for card, (x, y) in zip(layout, positions):
    width = int(card["width"])
    height = int(card["height"])
    card_bounds = (x, y, x + width, y + height)
    draw.rounded_rectangle((x, y, x + width, y + height), radius=16, fill=EXPORT_CARD_COLOR)

    title_y = y + 8
    draw.text((x + 10, title_y), str(card["title"]), font=title_font, fill=EXPORT_TEXT_PRIMARY)
    cursor_y = title_y + EXPORT_TITLE_SIZE + 10

    stats = list(card["stats"])
    if stats:
      stat_width = (width - (EXPORT_PADDING * 2) - EXPORT_INNER_GAP) // 2
      row_start_y = cursor_y
      row_max_height = 0
      for index, (label, value) in enumerate(stats):
        col = index % 2
        local_x = x + EXPORT_PADDING + col * (stat_width + EXPORT_INNER_GAP)
        local_y = row_start_y
        block_height = _measure_stat_block_height(value, stat_width)
        _assert_rect_within(
          card_bounds,
          (local_x, local_y, local_x + stat_width, local_y + block_height),
          f"{card['title']} stats",
        )
        draw.rounded_rectangle(
          (local_x, local_y, local_x + stat_width, local_y + block_height),
          radius=10,
          fill=EXPORT_GROUP_COLOR,
        )
        draw.text((local_x + 8, local_y + 6), label, font=label_font, fill=EXPORT_TEXT_MUTED)
        _draw_wrapped_text(draw, (local_x + 8, local_y + 23), value, value_font, EXPORT_TEXT_PRIMARY, stat_width - 16)
        row_max_height = max(row_max_height, block_height)
        if col == 1 or index == len(stats) - 1:
          row_start_y += row_max_height + EXPORT_INNER_GAP
          row_max_height = 0
      cursor_y = row_start_y
      cursor_y += 2

    items = list(card["items"])
    if items:
      item_columns = int(card["item_columns"])
      item_width = (width - (EXPORT_PADDING * 2) - (EXPORT_INNER_GAP * (item_columns - 1))) // item_columns
      row_max_height = 0
      row_start_y = cursor_y
      for index, item in enumerate(items):
        col = index % item_columns
        local_x = x + EXPORT_PADDING + col * (item_width + EXPORT_INNER_GAP)
        local_y = row_start_y
        block_height = _measure_item_block_height(item, item_width)
        _assert_rect_within(
          card_bounds,
          (local_x, local_y, local_x + item_width, local_y + block_height),
          f"{card['title']} items",
        )
        draw.rounded_rectangle(
          (local_x, local_y, local_x + item_width, local_y + block_height),
          radius=10,
          fill=ITEM_CARD_FG_COLOR[1],
        )
        inner_y = local_y + 6
        inner_y += _draw_wrapped_text(draw, (local_x + 8, inner_y), item.get("title", ""), body_bold_font, EXPORT_TEXT_PRIMARY, item_width - 16)
        inner_y += 1
        inner_y += _draw_wrapped_text(draw, (local_x + 8, inner_y), item.get("subtitle", ""), body_font, EXPORT_TEXT_PRIMARY, item_width - 16)
        inner_y += 4
        meta_left = item.get("meta_left", "")
        meta_right = item.get("meta_right", "")
        if meta_left or meta_right:
          _draw_wrapped_text(draw, (local_x + 8, inner_y), f"{meta_left} {meta_right}".strip(), meta_font, EXPORT_TEXT_MUTED, item_width - 16)
        row_max_height = max(row_max_height, block_height)
        if col == item_columns - 1 or index == len(items) - 1:
          row_start_y += row_max_height + EXPORT_INNER_GAP
          row_max_height = 0

  image.save(path, format="PNG")


def export_data_image(path: str, data: dict) -> None:
  export_cards_image(path, build_cards_data(data))


def run_export_qa(output_path: str) -> None:
  export_data_image(output_path, build_qa_sample_data())
  if not os.path.isfile(output_path):
    raise RuntimeError("QA export did not produce an output file.")


def build_cards_data(data: dict) -> list[dict[str, object]]:
  computer = data.get("computer") or {}
  cpu = data.get("cpu") or {}
  gpus = _normalize_items(data.get("gpu"))
  storage_items = _normalize_items(data.get("storage"))
  displays = _normalize_items(data.get("displays"))
  system_name = _normalized_system_name(
    computer.get("Manufacturer"),
    computer.get("Model"),
  )

  graphics_items: list[dict[str, str]] = []
  for index, gpu in enumerate(gpus, start=1):
    graphics_items.append({
      "title": f"GPU {index}",
      "subtitle": _coalesce(gpu.get("Name")),
      "meta_left": "VRAM",
      "meta_right": _bytes_to_gib_text(gpu.get("AdapterRAM")),
    })
  if not graphics_items:
    graphics_items.append({
      "title": "Graphics",
      "subtitle": "No graphics adapters detected.",
      "meta_left": "",
      "meta_right": "",
    })

  storage_items_grid: list[dict[str, str]] = []
  for index, disk in enumerate(storage_items, start=1):
    storage_items_grid.append({
      "title": f"Drive {index}",
      "subtitle": _coalesce(disk.get("FriendlyName")),
      "meta_left": _coalesce(disk.get("MediaType")),
      "meta_right": f"{_coalesce(disk.get('BusType'))} | {_bytes_to_gib_text(disk.get('Size'))}",
    })
  if not storage_items_grid:
    storage_items_grid.append({
      "title": "Storage",
      "subtitle": "No fixed storage devices detected.",
      "meta_left": "",
      "meta_right": "",
    })

  display_items: list[dict[str, str]] = []
  for index, display in enumerate(displays, start=1):
    width = _coalesce(display.get("Width"))
    height = _coalesce(display.get("Height"))
    primary = "Primary" if bool(display.get("Primary")) else "Secondary"
    display_items.append({
      "title": f"Display {index}",
      "subtitle": f"{width} x {height}",
      "meta_left": "Role",
      "meta_right": primary,
    })
  if not display_items:
    display_items.append({
      "title": "Displays",
      "subtitle": "No displays detected.",
      "meta_left": "",
      "meta_right": "",
    })

  return [
    {
      "title": "System",
      "stats": [
        ("System", system_name),
        ("Memory", _bytes_to_gib_text(computer.get("TotalPhysicalMemory"))),
      ],
      "items": [],
    },
    {
      "title": "Processor",
      "stats": [
        ("CPU", _coalesce(cpu.get("Name"))),
        ("Cores", _coalesce(cpu.get("NumberOfCores"))),
        ("Threads", _coalesce(cpu.get("NumberOfLogicalProcessors"))),
        ("Max Clock", _mhz_to_ghz_text(cpu.get("MaxClockSpeed"))),
      ],
      "items": [],
    },
    {
      "title": "Graphics",
      "stats": [
        ("Adapters", str(len(gpus) or 0)),
      ],
      "items": graphics_items,
    },
    {
      "title": "Storage",
      "stats": [
        ("Drives", str(len(storage_items) or 0)),
      ],
      "items": storage_items_grid,
    },
    {
      "title": "Displays",
      "stats": [
        ("Displays", str(len(displays) or 0)),
      ],
      "items": display_items,
    },
  ]


def collect_specs() -> dict:
  if os.name != "nt":
    raise RuntimeError("This app supports Windows only.")

  ps_script = r"""
$ErrorActionPreference = 'SilentlyContinue'

function Get-JsonSafeArray($value) {
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) { return $value }
  return @($value)
}

$computer = Get-CimInstance Win32_ComputerSystem |
  Select-Object Manufacturer, Model, TotalPhysicalMemory

$cpu = Get-CimInstance Win32_Processor |
  Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed

$gpu = Get-CimInstance Win32_VideoController |
  Select-Object Name, AdapterRAM

$physicalDisk = Get-PhysicalDisk |
  Select-Object FriendlyName, MediaType, BusType, Size

if (-not $physicalDisk) {
  $physicalDisk = Get-CimInstance Win32_DiskDrive |
    Select-Object @{Name='FriendlyName';Expression={$_.Model}},
                  @{Name='MediaType';Expression={$_.MediaType}},
                  @{Name='BusType';Expression={$_.InterfaceType}},
                  Size
}

$screens = @()
Add-Type -AssemblyName System.Windows.Forms
foreach ($screen in [System.Windows.Forms.Screen]::AllScreens) {
  $screens += [pscustomobject]@{
    Name = $screen.DeviceName
    Width = $screen.Bounds.Width
    Height = $screen.Bounds.Height
    Primary = $screen.Primary
  }
}

$result = [pscustomobject]@{
  computer = $computer
  cpu = $cpu
  gpu = (Get-JsonSafeArray $gpu)
  storage = (Get-JsonSafeArray $physicalDisk)
  displays = $screens
}

$result | ConvertTo-Json -Depth 6 -Compress
"""

  completed = subprocess.run(
    [
      "powershell",
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-Command",
      ps_script,
    ],
    capture_output=True,
    text=True,
    check=False,
  )

  if completed.returncode != 0:
    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    detail = stderr or stdout or f"PowerShell failed with exit code {completed.returncode}."
    raise RuntimeError(detail)

  payload = (completed.stdout or "").strip()
  if not payload:
    raise RuntimeError("PowerShell returned no hardware data.")

  try:
    return json.loads(payload)
  except json.JSONDecodeError as e:
    raise RuntimeError(f"Failed to parse hardware data: {e}") from e


def build_summary_text(data: dict) -> str:
  lines: list[str] = []
  for card in build_cards_data(data):
    lines.append(str(card["title"]))
    for label, value in card["stats"]:
      lines.append(f"{label}: {value}")
    for item in card["items"]:
      title = str(item.get("title", "")).strip()
      subtitle = str(item.get("subtitle", "")).strip()
      meta_left = str(item.get("meta_left", "")).strip()
      meta_right = str(item.get("meta_right", "")).strip()
      if title:
        lines.append(title)
      if subtitle:
        lines.append(f"  {subtitle}")
      if meta_left or meta_right:
        lines.append(f"  {meta_left}: {meta_right}".strip())
    lines.append("")

  return "\n".join(lines).strip()


class HardwareSpecsApp(ctk.CTk):
  def __init__(self):
    super().__init__()

    self.config_data = load_or_create_config(PATH_CONFIG_JSON)

    ctk.set_appearance_mode(self.config_data.get("appearance_mode", "System"))
    ctk.set_default_color_theme(self.config_data.get("color_theme", "blue"))

    width = self.config_data.get("window", {}).get("width", 980)
    height = self.config_data.get("window", {}).get("height", 760)

    self.title(APP_TITLE)
    self.geometry(f"{width}x{height}")
    self.minsize(1080, 720)

    set_window_icon(
      self,
      os.path.join(PATH_DIR_SCRIPT, "icon.ico"),
      os.path.join(PATH_DIR_SCRIPT, "icon.png"),
    )

    self._ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
    self._worker_thread: threading.Thread | None = None
    self._latest_data: dict | None = None
    self._card_frames: list[ctk.CTkFrame] = []

    self._build_ui()
    self.protocol("WM_DELETE_WINDOW", self._on_close)
    self.after(120, self._poll_queue)
    self.after(80, self.refresh_specs)
    self.bind("<Configure>", self._on_window_configure)

  def _build_ui(self) -> None:
    self.grid_columnconfigure(0, weight=1)
    self.grid_rowconfigure(2, weight=1)

    self.header_frame = ctk.CTkFrame(self)
    self.header_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
    self.header_frame.grid_columnconfigure(0, weight=1)

    self.title_label = ctk.CTkLabel(
      self.header_frame,
      text="Hardware Specs",
      font=ctk.CTkFont(size=24, weight="bold"),
    )
    self.title_label.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

    self.subtitle_label = ctk.CTkLabel(
      self.header_frame,
      text="Current workstation configuration overview.",
      font=ctk.CTkFont(size=13),
      text_color=("gray35", "gray75"),
    )
    self.subtitle_label.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")

    self.controls_frame = ctk.CTkFrame(self)
    self.controls_frame.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")
    self.controls_frame.grid_columnconfigure(1, weight=1)

    self.refresh_button = ctk.CTkButton(
      self.controls_frame,
      text="Refresh",
      command=self.refresh_specs,
      width=120,
    )
    self.refresh_button.grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")

    self.copy_button = ctk.CTkButton(
      self.controls_frame,
      text="Copy Summary",
      command=self.copy_summary,
      width=140,
    )
    self.copy_button.grid(row=0, column=1, padx=6, pady=10, sticky="w")

    self.save_image_button = ctk.CTkButton(
      self.controls_frame,
      text="Save Image",
      command=self.save_image,
      width=130,
    )
    self.save_image_button.grid(row=0, column=2, padx=6, pady=10, sticky="w")

    self.status_label = ctk.CTkLabel(
      self.controls_frame,
      text="Loading hardware details...",
      font=ctk.CTkFont(size=13),
      text_color=("gray35", "gray75"),
    )
    self.status_label.grid(row=0, column=3, padx=(6, 12), pady=10, sticky="e")

    self.cards_frame = ctk.CTkScrollableFrame(self, corner_radius=16)
    self.cards_frame.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
    self.cards_frame.grid_columnconfigure(0, weight=1)
    self.cards_frame.grid_columnconfigure(1, weight=1)
    self.cards_frame.grid_rowconfigure(0, weight=1)
    self.cards_frame.grid_rowconfigure(1, weight=1)
    self.cards_frame.grid_rowconfigure(2, weight=1)

    self._show_message_card("Loading hardware details...")

  def _clear_cards(self) -> None:
    for frame in self._card_frames:
      frame.destroy()
    self._card_frames.clear()

  def _create_stat_grid(self, parent, stats: list[tuple[str, str]]) -> None:
    if not stats:
      return

    stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
    stats_frame.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="ew")
    for column in range(2):
      stats_frame.grid_columnconfigure(column, weight=1)

    for index, (label, value) in enumerate(stats):
      stat_card = ctk.CTkFrame(stats_frame, corner_radius=10, fg_color=GROUP_CARD_FG_COLOR)
      stat_card.grid(row=index // 2, column=index % 2, padx=3, pady=3, sticky="nsew")
      stat_label = ctk.CTkLabel(
        stat_card,
        text=label,
        font=ctk.CTkFont(size=11, weight="bold"),
        anchor="w",
        text_color=("gray35", "gray75"),
      )
      stat_label.grid(row=0, column=0, padx=8, pady=(6, 1), sticky="w")
      stat_value = ctk.CTkLabel(
        stat_card,
        text=value,
        font=ctk.CTkFont(size=13, weight="bold"),
        anchor="w",
        justify="left",
        wraplength=200,
      )
      stat_value.grid(row=1, column=0, padx=8, pady=(0, 6), sticky="w")

  def _create_item_grid(self, parent, items: list[dict[str, str]], columns: int = 2) -> None:
    if not items:
      return

    items_frame = ctk.CTkFrame(parent, fg_color="transparent")
    items_frame.grid(row=2, column=0, padx=10, pady=(0, 6), sticky="nsew")
    for column in range(columns):
      items_frame.grid_columnconfigure(column, weight=1)

    for index, item in enumerate(items):
      item_card = ctk.CTkFrame(items_frame, corner_radius=10, fg_color=ITEM_CARD_FG_COLOR)
      item_card.grid(row=index // columns, column=index % columns, padx=3, pady=3, sticky="nsew")
      item_card.grid_columnconfigure(0, weight=1)

      title = ctk.CTkLabel(
        item_card,
        text=item["title"],
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="w",
      )
      title.grid(row=0, column=0, padx=8, pady=(6, 1), sticky="ew")

      subtitle = ctk.CTkLabel(
        item_card,
        text=item["subtitle"],
        font=ctk.CTkFont(size=12),
        anchor="w",
        justify="left",
        wraplength=220,
      )
      subtitle.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="ew")

      meta_left = item.get("meta_left", "")
      meta_right = item.get("meta_right", "")
      if meta_left or meta_right:
        meta = ctk.CTkLabel(
          item_card,
          text=f"{meta_left}  {meta_right}".strip(),
          font=ctk.CTkFont(size=11),
          anchor="w",
          justify="left",
          text_color=("gray35", "gray75"),
        )
        meta.grid(row=2, column=0, padx=8, pady=(0, 6), sticky="ew")

  def _create_card(
    self,
    title: str,
    stats: list[tuple[str, str]],
    items: list[dict[str, str]],
    *,
    column: int,
    row: int,
    item_columns: int = 2,
  ) -> None:
    card = ctk.CTkFrame(self.cards_frame, corner_radius=16, fg_color=CARD_FG_COLOR)
    card.grid(row=row, column=column, padx=5, pady=5, sticky="nsew")
    card.grid_columnconfigure(0, weight=1)
    card.grid_rowconfigure(2, weight=1)
    self._card_frames.append(card)

    title_label = ctk.CTkLabel(
      card,
      text=title,
      font=ctk.CTkFont(size=18, weight="bold"),
      anchor="w",
    )
    title_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 6), sticky="ew")

    self._create_stat_grid(card, stats)
    self._create_item_grid(card, items, columns=item_columns)

  def _render_cards(self, data: dict) -> None:
    self._clear_cards()
    cards = build_cards_data(data)
    for index, card in enumerate(cards):
      title = str(card["title"])
      stats = list(card["stats"])
      items = list(card["items"])
      if index < 2:
        self._create_card(title, stats, items, column=index, row=0, item_columns=2)
      elif index < 4:
        self._create_card(title, stats, items, column=index - 2, row=1, item_columns=2)
      else:
        self._create_card(title, stats, items, column=0, row=2, item_columns=4)
        self._card_frames[-1].grid(columnspan=2)

  def _show_message_card(self, message: str) -> None:
    self._clear_cards()
    self._create_card("Status", [("Details", message)], [], column=0, row=0)
    self._card_frames[-1].grid(columnspan=2)

  def _on_window_configure(self, _event=None) -> None:
    width = max(840, self.winfo_width() - 180)
    wraplength = max(180, min(260, width // 5))
    for card in self._card_frames:
      for child in card.winfo_children():
        for grandchild in child.winfo_children():
          if isinstance(grandchild, ctk.CTkLabel) and str(grandchild.cget("justify")) == "left":
            grandchild.configure(wraplength=wraplength)

  def refresh_specs(self) -> None:
    if self._worker_thread and self._worker_thread.is_alive():
      return

    self.refresh_button.configure(state="disabled")
    self.copy_button.configure(state="disabled")
    self.save_image_button.configure(state="disabled")
    self.status_label.configure(text="Refreshing...")
    self._show_message_card("Collecting hardware details...")

    def worker() -> None:
      try:
        data = collect_specs()
        self._ui_queue.put(("success", {"data": data}))
      except Exception as e:
        self._ui_queue.put(("error", str(e)))

    self._worker_thread = threading.Thread(target=worker, daemon=True)
    self._worker_thread.start()

  def copy_summary(self) -> None:
    if not self._latest_data:
      return

    summary = build_summary_text(self._latest_data)
    self.clipboard_clear()
    self.clipboard_append(summary)
    self.status_label.configure(text="Summary copied.")

  def save_image(self) -> None:
    if not self._latest_data:
      return

    default_name = "hardware-specs.png"
    path = filedialog.asksaveasfilename(
      title="Save Hardware Specs Image",
      defaultextension=".png",
      initialfile=default_name,
      filetypes=[("PNG Image", "*.png")],
    )
    if not path:
      return

    try:
      export_cards_image(path, build_cards_data(self._latest_data))
      self.status_label.configure(text="Image saved.")
    except Exception as e:
      self.status_label.configure(text="Image save failed.")
      self._show_message_card(f"Failed to save image.\n\n{e}")

  def _poll_queue(self) -> None:
    try:
      while True:
        kind, payload = self._ui_queue.get_nowait()
        if kind == "success":
          data = payload["data"]
          self._latest_data = data
          self._render_cards(data)
          self.status_label.configure(text="Hardware details loaded.")
          self.copy_button.configure(state="normal")
          self.save_image_button.configure(state="normal")
          self.refresh_button.configure(state="normal")
        elif kind == "error":
          self._latest_data = None
          self._show_message_card(f"Failed to collect hardware details.\n\n{payload}")
          self.status_label.configure(text="Load failed.")
          self.copy_button.configure(state="disabled")
          self.save_image_button.configure(state="disabled")
          self.refresh_button.configure(state="normal")
    except queue.Empty:
      pass

    self.after(120, self._poll_queue)

  def _on_close(self) -> None:
    try:
      width = int(self.winfo_width())
      height = int(self.winfo_height())
      self.config_data["window"] = {"width": width, "height": height}
      _write_json_atomic(PATH_CONFIG_JSON, self.config_data)
    except Exception:
      pass
    self.destroy()


def main(argv: list[str] | None = None) -> int:
  argv = list(sys.argv[1:] if argv is None else argv)

  parser = argparse.ArgumentParser(description="Hardware specs viewer and exporter.")
  parser.add_argument("--export-image", help="Export a single PNG and exit.")
  parser.add_argument("--qa-export", help="Render the built-in QA sample to a PNG and exit.")
  parser.add_argument("--sample-json", help="Use JSON input instead of live hardware collection for export.")
  args = parser.parse_args(argv)

  if args.qa_export:
    run_export_qa(os.path.abspath(args.qa_export))
    return 0

  if args.export_image:
    if args.sample_json:
      data = _read_json(os.path.abspath(args.sample_json))
      if not isinstance(data, dict):
        raise RuntimeError(f"Failed to load sample JSON: {args.sample_json}")
    else:
      data = collect_specs()
    export_data_image(os.path.abspath(args.export_image), data)
    return 0

  set_windows_app_user_model_id(APP_USER_MODEL_ID)
  app = HardwareSpecsApp()
  app.mainloop()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
