#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# MIT License
#
# Copyright © 2019 Sir Nickolas
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from __future__ import unicode_literals

import ast
import contextlib
import errno
import io
import multiprocessing
import os.path
import pprint
import re
import shutil
import sys
import time
import traceback

if sys.version_info.major <= 2:
    from cStringIO import StringIO as BytesIO
    from future_builtins import map, zip

    input = raw_input
    range = xrange
else:
    basestring = unicode = str
    BytesIO = io.BytesIO

try:
    import threading
    try:
        import queue
    except ImportError:
        import Queue as queue # Python 2.
except ImportError: # Python <3.7 теоретически может быть собран без поддержки многопоточности.
    threading = queue = None

try:
    from PIL import Image
except ImportError:
    Image = None


VERSION = "1.001"
DEFAULT_LOG_PATH = "estool.log"
DEFAULT_CONFIG_PATH = "config.py"
SCALING_FACTOR = 2. / 3.
SCRIPT_EXTS = {".rpy"}
IMAGE_EXTS = {".jpg", ".png", ".webp", ".jpeg"}

CONFIG_TEMPLATE = """\
# Конфиг для ESTool v{version}.
{{

# Если `True`, выполняется тестовый прогон. Он ничего не меняет и не создает никаких файлов
# (кроме лога), но выявляет большую часть ошибок. Настоятельно рекомендуется сначала запустить
# с `True`, посмотреть лог, все ли верно отработало, и только потом сменить на `False`.
"dry_run": True,

# Если `False`, то портированный мод кладется в отдельную папку рядом. Если `True`, то он кладется
# *вместо* исходных файлов. С `True` работает быстрее за счет того, что не приходится копировать
# музыку и видео.
# Внимание: если вы поставите `True` и накосячите, то исправить будет СЛОЖНО. Если не уверены
# на 100% - лучше не трогайте эту настройку.
"in_place": False,

# При "in_place":True делаются резервные копии .rpy-скриптов (только скриптов!).
# Эта настройка задает, куда их класть:
# * Если "separate", то бэкапы создаются в отдельной папке (см. ниже).
# * Если "nearby", то бэкапы кладутся рядом с исходными файлами (с расширением ._rpy).
# * Если "none", то бэкапы НЕ создаются вообще.
# При "in_place":False эта настройка игнорируется (в бэкапах нет необходимости, поскольку исходные
# файлы остаются в целости и сохранности).
"backup_style": {default_backup_style},

# При "backup_style":"separate" задает путь к папке с бэкапами. В него можно вписать
# дату и/или время. Полный перечень %-спецификаторов: http://strftime.org
"backup_location": "backups/%y-%m-%d_%H.%M.%S",

# Путь к папке с модом, который требуется портировать.
"src_path": "samantha7stm",

# Путь, куда класть результат. При "in_place":True переименовывает "src_path" в "dest_path".
"dest_path": "Samantha",

# Если `True`, переименовывает файлы, чтобы в названиях была только латиница и базовая пунктуация.
# Кириллица транслитерируется на латинский.
"rename_non_ascii": True,

# Если `True`, умножает координаты в коде на 2/3.
"rescale_coordinates": True,

# К каждой строке кода, где были изменены координаты, дописывается комментарий особого вида.
# Эта настройка задает его тип:
# * Если "long", то в комментарий пишется исходная строка целиком.
# * Если "short", то просто делается пометка, что строка была изменена.
# * Если "none", то не дописывается никакого комментария. Внимание: если при "in_place":True
#   запустить скрипт два раза подряд с "none", то координаты будут изменены дважды! Остальные режимы
#   защищены от такого.
"comments_style": "long",

# Если `True`, сжимает изображения (в полтора раза). Требует наличия Python Image Library (PIL).
# Внимание: если при "in_place":True запустить скрипт два раза, картинки будут сжаты дважды!
"resize_images": True,

# Если в коде скриптов для доступа к файлам используется какой-то префикс, не отраженный в структуре
# каталогов (например, "mods/"), следует вписать его сюда. Иначе не будет работать замена путей.
"old_virtual_root": "",

# Аналогично, если в ходе портирования требуется добавить такой префикс, он указывается здесь.
"new_virtual_root": "Samantha",

# Шаблоны файлов, которые следует исключить из мода. `?` - любой одиночный символ,
# `*` - любое количество любых символов, `**` - любые подпапки.
# Внимание: при "in_place":True эти файлы будут УДАЛЕНЫ!
"exclude_patterns": [
    "**.rpyc", # Скомпилированные в байт-код скрипты.
    # "**/*.rpyc", # Эквивалентно выше написанному.
    "**/Thumbs.db", # Свойства папки (Windows).
    "**/.DS_Store", # Свойства папки (macOS).
    "**._rpy", # Наши бэкапы стиля "nearby" (старые удаляются, новые создаются).
],

# Правила по перемещению файлов. Задаются тройками: (префикс, шаблон, новый_префикс). Если путь
# к файлу начинается с указанного префикса и удовлетворяет шаблону, то этот префикс срезается и
# заменяется новым. Файл копируется/перемещается (в зависимости от "in_place") в новое место;
# также переписываются пути в скриптах.
# Правила пытаются примениться последовательно, так что порядок объявления важен.
"path_rewrite_rules": [
    # (prefix_to_strip, glob_to_test, prefix_to_prepend),
    ("/samantha/sprites.rpy", "",      "/ss_sprites.rpy"),
    ("/samantha/",            "*.rpy", "/"),
    ("/images/1080/bg/",      "**",    "/samantha/image/"),
    ("/images/1080/",         "**",    "/samantha/image/"),
    # Под это правило попадают все загружаемые в скриптах файлы, но оно ничего не меняет.
    # Необходимо для корректного переписывания путей в коде.
    ("/samantha/",            "**",    "/samantha/"),
],

# Дополнительные файлы, которые требуется добавить в мод.
"extra_files": [
    # (src, dest),
    ("sprites_lol.rpy", "/"),
],

}}
"""

SCRIPT_POSTFIX = ("""\
# Android version created with ESTool v%s
# More info here: https://vk.com/topic-93304648_35130916
""" % VERSION).replace("\n", os.linesep).encode("utf-8")

# Мы используем байтовые регулярные выражения, чтобы не тратить время на раскодирование файлов.
COORD_RE = re.compile(br"""
    # ...color = (...)
    color \s* =?
    [\d\s\[\](),+-]+
|   # prefix %d | prefix = %d
    (?:\b | (?<=\d))
    (?:
        [xy] (?:align | anchor | center | maximum | minimum | offset | pos | size)
    |   (?:bottom | left | right | top)_padding | height | width | size
    )
    (?:\s | \s* =)
    [\s+-]* (\d+)
    (?![\d.])
|   # prefix(%d, %d)
    (?:\b | (?<=\d))
    (?:
        (?:im \s* \. \s* Composite | at \s+ Zoom | LiveComposite | Zooming) \s* \(
    |   align | corner[12] | anchor | pos | (?:max)? size
    )
    \s* \(
    [\s+-]* \d+
    \s* ,
    [\s+-]* \d+
    \s* \)
|   # at Move((%d, %d), (%d, %d)
    (?:\b | (?<=\d))
    at \s+ Move \s* \( \s*
    [\[(] [\d\s,+-]+ [\])]
    \s* , \s*
    [\[(] [\d\s,+-]+ [\])]
|   # (%d, %d, %d, %d)
    [\[(]
    [\s+-]* \d+
    \s* ,
    [\s+-]* \d+
    \s* ,
    [\s+-]* \d+
    \s* ,
    [\s+-]* \d+
    \s* [\])]
|   # , %d, %d)
    ,
    [\s+-]* \d+
    \s* ,
    [\s+-]* \d+
    \s* \)
""", re.X)

NUMBER_RE = re.compile(br"\d+")

IMAGE_RE = re.compile(br"\bimage\s+(\d[^\s=]*)")

CYRILLIC = {
    "а": "a",  "б": "b",  "в": "v",  "г": "g",  "д": "d",  "е": "e",  "ё": "yo", "ж": "zh",
    "з": "z",  "и": "i",  "й": "iy", "к": "k",  "л": "l",  "м": "m",  "н": "n",  "о": "o",
    "п": "p",  "р": "r",  "с": "s",  "т": "t",  "у": "u",  "ф": "f",  "х": "h",  "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sh", "ы": "i",  "э": "e",  "ю": "y",  "я": "ya",
    # Твердый и мягкий знаки заменяются подчеркиванием на общих основаниях.
}

DIGIT_NAMES = {
    b"0": b"zero",  b"1": b"one",  b"2": b"two",    b"3": b"three",  b"4": b"four",
    b"5": b"five",  b"6": b"six",  b"7": b"seven",  b"8": b"eight",  b"9": b"nine",
}


class Stats:
    def __init__(self):
        self.scripts_processed = 0
        self.lines_modified = 0
        self.images_processed = 0
        self.files_copied = 0
        self.files_moved = 0
        self.files_deleted = 0
        self.files_ignored = 0
        self.failures = 0

    def __iadd__(self, another):
        self.scripts_processed += another.scripts_processed
        self.lines_modified += another.lines_modified
        self.images_processed += another.images_processed
        self.files_copied += another.files_copied
        self.files_moved += another.files_moved
        self.files_deleted += another.files_deleted
        self.files_ignored += another.files_ignored
        self.failures += another.failures
        return self


class FType:
    SCRIPT  = 0
    IMAGE   = 1
    FOREIGN = 2
    OTHER   = 3


class Task:
    COPY   = 0
    MOVE   = 1
    REMOVE = 2
    SCRIPT = 3
    IMAGE  = 4


class BackupStyle:
    NONE     = 0
    NEARBY   = 1
    SEPARATE = 2


class CommentsStyle:
    NONE  = 0
    SHORT = 1
    LONG  = 2


# Глобальные переменные.
log_file = None
cfg = None


def parse_args():
    import argparse

    p = argparse.ArgumentParser(
        description="Port an Everlasting Summer mod to mobile platforms.",
        fromfile_prefix_chars="@",
    )
    p.add_argument("-V", "--version",
        help="print the version and exit",
        action="version",
        version="ESTool v" + VERSION,
    )
    p.add_argument("-w", "--keep-cwd",
        help="do not chdir into the script's directory",
        action="store_true",
    )
    p.add_argument("--log",
        help="path to the log file (default: %(default)s)",
        default=DEFAULT_LOG_PATH,
    )
    p.add_argument("-c", "--config",
        help="path to the config file (default: %s)" % DEFAULT_CONFIG_PATH,
        default="", # Нам нужно уметь распознавать, что мы вызваны без этого ключа.
    )
    return p.parse_args()


if os.path.altsep is None:
    def norm_seps(path): return path
else:
    def norm_seps(path):
        return path.replace(os.path.altsep, os.path.sep)


@contextlib.contextmanager
def suppress_os_error(code):
    try:
        yield
    except OSError as e:
        if e.errno != code:
            raise # Если ошибка не та, которая нас интересует, отправляем исключение дальше.


def make_dirs(path):
    with suppress_os_error(errno.EEXIST):
        os.makedirs(path or os.path.curdir)


def log(text, stdout=True):
    # https://stackoverflow.com/questions/4545661/unicodedecodeerror-when-redirecting-to-file
    uni = text
    if sys.version_info.major <= 2:
        if isinstance(text, bytes):
            uni = text.decode("utf-8", errors="replace")
        else:
            text = text.encode("utf-8")
        text += b"\n"
    else:
        text += "\n"
    uni += "\n"
    # Мы используем `f.write(x + "\n")` вместо `print(x, file=f)`, потому что первый вариант
    # потокобезопасен и не нуждается в синхронизации.
    if stdout:
        sys.stdout.write(text)
    log_file.write(uni)


def fail(msg, *args):
    log("EPIC FAIL: " + msg % args)
    sys.exit(1)


# Обработка конфига.

def generate_config(filename):
    import platform

    on_android = platform.machine().startswith("arm")
    text = CONFIG_TEMPLATE.format(
        version=VERSION,
        default_backup_style='"nearby"' if on_android else '"separate"',
    )
    make_dirs(os.path.dirname(filename))
    with io.open(filename, "w", encoding="utf-8") as f:
        f.write(text)


def read_config(args):
    try:
        with io.open(args.config or DEFAULT_CONFIG_PATH, encoding="utf-8-sig") as f:
            text = f.read()
    except IOError as e:
        # Если пользователь указал несуществующий путь к конфигу (или это вообще другая ошибка),
        # материм его.
        if e.errno != errno.ENOENT or args.config:
            raise
        # Мы не нашли конфига в дефолтном месте; создаем его и выходим.
        generate_config(DEFAULT_CONFIG_PATH)
        log("Dumped a sample config.")
        sys.exit()

    # Парсим конфиг.
    return ast.literal_eval(text)


def decode_byte_strings(x):
    # Преобразуем `str` в `unicode` на Python 2.
    if isinstance(x, bytes):
        return x.decode("utf-8")
    if isinstance(x, (tuple, list)):
        return type(x)(map(decode_byte_strings, x))
    if isinstance(x, dict):
        for key, value in x.iteritems():
            x[key] = decode_byte_strings(value)
    return x


def validate(key, check):
    try:
        # Валидатор принимает значение и должен либо вернуть его (возможно, изменив),
        # либо выкинуть исключение.
        return check(cfg.get(key))
    except Exception: # `SystemExit` не наследуется от `Exception` и потому пролетает мимо.
        fail('Invalid option "%s" in the config.', key)


def validate_if(cond, result):
    if cond:
        return result
    raise Exception


def validate_opt(check, default=None):
    return lambda x: check(x) if x is not None else default


def validate_type(*types):
    return lambda x: validate_if(isinstance(x, types), x)


def validate_enum(namespace):
    return lambda x: validate_if(x.islower(), getattr(namespace, x.upper()))


def validate_not_str(x):
    return validate_if(not isinstance(x, basestring), x)


def validate_list(check):
    # Строки тоже итерируемы (и их элементами являются строки), так что их нужно исключить.
    return lambda x: list(map(check, validate_not_str(x)))


def validate_tuple(*checks):
    return lambda x: validate_if(
        len(x) == len(checks),
        tuple(f(y) for f, y in zip(checks, validate_not_str(x))),
    )


def validate_virtual_root(path):
    path = path.strip("/\\")
    return path and path.replace("\\", "/") + "/"


def validate_rewrite_rule_prefix(prefix):
    # Мы не считаем апостроф допустимым символом для путей, так что избавляемся от него.
    return prefix.lstrip("/\\").replace("\\", "/").replace("'", "_")


def validate_rewrite_rule_glob(glob):
    return glob.replace("'", "_")


def validate_extra_file(x):
    src, dest = validate_not_str(x)
    if not os.path.isfile(src):
        if os.path.exists(src):
            fail("Extra file '%s' is not a file.", src)
        else:
            fail("Cannot find extra file '%s'.", src)
    # Считаем, что целевой путь является директорией тогда и только тогда,
    # когда он оканчивается слешем.
    if not dest or dest.endswith(("/", "\\")):
        dest += os.path.basename(src)
    return norm_seps(src), norm_seps(dest.lstrip("/\\"))


def are_independent_paths(a, b):
    # Возвращает `False`, если директории совпадают или одна является предком другой.
    a = os.path.normcase(os.path.realpath(a))
    b = os.path.normcase(os.path.realpath(b))
    # На PyPy2 `os.path.realpath` почему-то может вернуть `str`, когда на вход подается `unicode`.
    if isinstance(a, bytes):
        a = a.decode("utf-8")
    if isinstance(b, bytes):
        b = b.decode("utf-8")
    if a > b:
        a, b = b, a
    # "/x" и "/xy" независимы, но "/x" и "/x/y"­ - нет.
    # Корень файловой системы ("/" или "C:\\") также дает `False`.
    return not b.startswith(a) or (len(b) > len(a) and a[-1] != os.path.sep != b[len(a)])


def convert_glob_to_re(pattern):
    # Мы считаем "f.txt" и "/f.txt" эквивалентными.
    pattern = pattern.lstrip("/\\")
    m = re.match(r"\*\*+[/\\]+", pattern)
    if m is not None:
        # Частный случай: **/ в начале шаблона. См. комментарий о /**/ ниже.
        result = ["(?:[^\x00-\x1F\"'*:<>?|]*[/\\\\]+)?"]
        pattern = pattern[m.end():]
    else:
        result = [r"[/\\]*"]

    last_pos = 0
    for m in re.finditer(r"[/\\]+(?:\*\*+[/\\]+)?|\*+|\?", pattern):
        result.append(re.escape(pattern[last_pos:m.start()]))
        last_pos = m.end()
        m0 = m.group()
        if m0 == "*":
            result.append("[^\x00-\x1F\"'*/:<>?\\\\|]*")
        elif m0 == "?":
            result.append("[^\x00-\x1F\"'*/:<>?\\\\|]")
        elif m0[0] == "*": # **
            result.append("[^\x00-\x1F\"'*:<>?|]*")
        elif "*" in m0: # /**/
            # Вынесено частным случаем, чтобы "a/f.txt" соответствовало шаблону "a/**/f.txt".
            result.append("[/\\\\]+(?:[^\x00-\x1F\"'*:<>?|]+[/\\\\]+)?")
        else: # /
            result.append(r"[/\\]+")

    result.append(re.escape(pattern[last_pos:]))
    return "".join(result)


def process_config():
    if not isinstance(cfg, dict): # Ну а вдруг?
        fail("Config must be a (brace-enclosed) `dict`.")
    if sys.version_info.major <= 2:
        decode_byte_strings(cfg)

    val_bool = validate_type(bool)
    val_str = validate_type(unicode)
    validate("dry_run", val_bool)
    validate("in_place", val_bool)
    cfg["src_path"]  = norm_seps(validate("src_path", val_str))
    cfg["dest_path"] = norm_seps(validate("dest_path", val_str))
    if not os.path.isdir(cfg["src_path"]):
        fail("Cannot find '%s'.", cfg["src_path"])
    if not cfg["in_place"] and not are_independent_paths(cfg["src_path"], cfg["dest_path"]):
        fail('"src_path" and "dest_path" must be distinct and not contained one in another.')

    validate("rename_non_ascii", val_bool)
    validate("rescale_coordinates", val_bool)
    validate("resize_images", val_bool)
    if Image is None and cfg["resize_images"]:
        fail('"resize_images" is `True`, but Python Image Library (PIL) is not found.')

    cfg["old_virtual_root"] = validate("old_virtual_root", validate_virtual_root)
    cfg["new_virtual_root"] = validate("new_virtual_root", validate_virtual_root)
    validate("exclude_patterns", validate_list(val_str))
    cfg["path_rewrite_rules"] = validate("path_rewrite_rules", validate_list(validate_tuple(
        validate_rewrite_rule_prefix, validate_rewrite_rule_glob, validate_rewrite_rule_prefix,
    )))
    if len(cfg["old_virtual_root"].lstrip()) <= 2:
        # Проверяем, чтобы правила были достаточно четкими. Иначе регулярное выражение для замены
        # путей может срабатывать на произвольных фрагментах кода.
        heuristic = re.compile(r"\w[/\\]\W*\w", re.U)
        for prefix, glob, _ in cfg["path_rewrite_rules"]:
            if glob.lstrip("/\\"):
                vague = re.search(r"\w[/\\]", prefix, re.U) is None is heuristic.search(glob)
            else:
                vague = len(prefix.strip(" \t/\\")) <= 1
            if vague:
                fail(
                    "Rule (%r, %r, ...) is too vague."
                    " Please, refine it (preferably, the first and third parts).",
                    prefix, glob,
                )

    cfg["extra_files"] = validate("extra_files", validate_list(validate_extra_file))

    if cfg["in_place"]:
        cfg["_backup_style"] = validate("backup_style", validate_enum(BackupStyle))
    else:
        # Нет смысла создавать бэкап, если мы не портим исходную директорию.
        validate("backup_style", validate_opt(validate_enum(BackupStyle)))
        cfg["_backup_style"] = BackupStyle.NONE

    if cfg["_backup_style"] != BackupStyle.SEPARATE:
        validate("backup_location", validate_opt(time.strftime))
    else:
        cfg["_backup_location"] = norm_seps(validate("backup_location", time.strftime))
        # Проверяем, чтобы директории для бэкапов не существовало или хотя бы она была пустой.
        with suppress_os_error(errno.ENOENT):
            if os.listdir(cfg["_backup_location"]):
                fail('"backup_location" already exists and is not empty.')

    cfg["_comments_style"] = validate("comments_style", validate_enum(CommentsStyle))

    cfg["_exclude_regex"] = re.compile(
        r"(?:%s)\Z" % "|".join(map(convert_glob_to_re, cfg["exclude_patterns"]))
    )

    cfg["_path_rewrite_globs_src"] = [
        convert_glob_to_re(pattern) for _, pattern, _ in cfg["path_rewrite_rules"]
    ]
    cfg["_path_rewrite_globs"] = [
        re.compile(pattern + r"\Z") for pattern in cfg["_path_rewrite_globs_src"]
    ]
    cfg["_path_rewrite_regex"] = None # Создаются позже.
    cfg["_path_rewrite_repls"] = None


# Подготовка к работе, составление списка задач.

def is_ignored_path(path):
    return cfg["_exclude_regex"].match(path) is not None


def rewrite_path(path):
    # Изменяем путь согласно `path_rewrite_rules`.
    p = path.lstrip("/\\").replace("\\", "/").replace("'", "_")
    for (prefix, _, repl), glob in zip(cfg["path_rewrite_rules"], cfg["_path_rewrite_globs"]):
        if p.startswith(prefix) and glob.match(p, len(prefix)) is not None:
            return norm_seps(repl + p[len(prefix):])
    return path


def scan_for_files(root):
    prefix = len(root) + 1
    for path, _, files in os.walk(root):
        path = path[prefix:]
        for f in files:
            filename = os.path.join(path, f)
            yield filename, None if is_ignored_path(filename) else rewrite_path(filename)


def detect_file_type(path):
    # `.lower()` необходимо, поскольку иногда в модах встречаются файлы
    # с именами (и расширениями) в верхнем регистре. Увы.
    ext = os.path.splitext(path)[1].lower()
    if ext in SCRIPT_EXTS:
        return FType.SCRIPT
    elif ext in IMAGE_EXTS:
        return FType.IMAGE
    else:
        return FType.OTHER


def are_identical_files(a, b):
    # Быстрая проверка: файлы не могут совпадать, если у них разный размер.
    if os.path.getsize(a) != os.path.getsize(b):
        return False
    # Открываем и сравниваем побайтово.
    with open(a, "rb") as fa, open(b, "rb") as fb:
        chunk = b"1"
        while chunk:
            chunk = fa.read(16384)
            if chunk != fb.read(16384):
                return False
    return True


def collect_orphans(root, registry):
    # Ищем в `root` файлы, не упомянутые в `registry`.
    for path, _, files in os.walk(root):
        for f in files:
            f = os.path.join(path, f)
            if f not in registry:
                yield f


def collect_files(old_root, new_root):
    files = [ ]
    garbage = [ ]
    auto_renames = [ ]
    all_srcs = set()
    dest_src_map = { }
    rename_non_ascii = cfg["rename_non_ascii"]
    # Собираем внешние файлы, добавляемые в мод.
    for src, dest in cfg["extra_files"]:
        dest = os.path.join(new_root, dest)
        if dest in dest_src_map:
            fail(
                "Both '%s' and '%s' will end up as '%s'."
                ' Seems that you\'ve messed "extra_files" up.',
                dest_src_map[dest], src, dest,
            )
        dest_src_map[dest] = src
        all_srcs.add(src)
        files.append((FType.FOREIGN, src, dest))

    # Перебираем файлы мода.
    for src, dest in scan_for_files(old_root):
        if dest is None:
            garbage.append(os.path.join(old_root, src))
            continue

        renamed = "'" in src # Нужно для корректного функционирования наших регулярных выражений.
        if rename_non_ascii:
            dest, changes = re.subn(r"[^ -~]", lambda m: CYRILLIC.get(m.group().lower(), "_"), dest)
            if changes > 0:
                renamed = True
        if renamed:
            auto_renames.append((src, dest))

        src = os.path.join(old_root, src)
        dest = os.path.join(new_root, dest)
        if dest not in dest_src_map:
            dest_src_map[dest] = src
            all_srcs.add(src)
            files.append((detect_file_type(src), src, dest))
        else:
            # Пользователь хочет скопировать два разных файла в одно и то же место.
            if not are_identical_files(src, dest_src_map[dest]):
                fail(
                    "Both '%s' and '%s' will end up as '%s'."
                    ' Seems that you\'ve messed "path_rewrite_rules" up.',
                    dest_src_map[dest], src, dest,
                )
            # Если они совпадают с точностью до байта - нет проблем.
            garbage.append(src)

    for _, src, dest in files:
        if src != dest in all_srcs:
            fail(
                "Cannot move '%s' -> '%s' because the target file already exists."
                ' Set "in_place" to `False` if you *really* want to do that.',
                src, dest,
            )

    # Сортируем по убыванию длины, чтобы корректно обрабатывались случаи,
    # когда одно имя файла является префиксом другого.
    auto_renames.sort(key=lambda t: len(t[0]), reverse=True)
    return (
        files,
        garbage,
        list(collect_orphans(new_root, dest_src_map)) if old_root != new_root else [ ],
        auto_renames,
    )


def build_path_rewrite_regex(auto_renames):
    patterns = [ ]
    repls = [ ]
    # `auto_renames` в приоритете перед "path_rewrite_rules".
    for src, dest in auto_renames:
        # `()` - чтобы детектить совпадение через `m.lastindex`.
        patterns.append(re.escape(src.encode("utf-8")) + b"()")
        repls.append(dest)

    for (prefix, _, repl), glob in zip(cfg["path_rewrite_rules"], cfg["_path_rewrite_globs_src"]):
        # Python >=3,<3.5 не поддерживает %-форматирование байтовых строк.
        patterns.append(re.escape(prefix.encode("utf-8")) + b"(" + glob.encode("utf-8") + b")")
        repls.append(repl)

    cfg["_path_rewrite_regex"] = re.compile(b"".join((
        # Здесь, и только здесь, мы считаем, что пробел (\x20) может быть разделителем путей.
        b"(?<![^\x00- \"'*:<>?|])",
        re.escape(cfg["old_virtual_root"].encode("utf-8")),
        b"(?:",
        b"|".join(patterns),
        b")(?![^\x00- \"'*:<>?|])",
    )))

    new_virtual_root = cfg["new_virtual_root"].encode("utf-8")
    cfg["_path_rewrite_repls"] = [new_virtual_root + repl.encode("utf-8") for repl in repls]


def is_newer(a, b):
    with suppress_os_error(errno.ENOENT):
        return os.path.getmtime(a) > os.path.getmtime(b)
    # Как минимум одного из файлов не существует.
    return True


def generate_tasks(files, src_garbage, dest_garbage):
    in_place = cfg["in_place"]
    images_enabled = cfg["resize_images"]
    tasks = [(Task.REMOVE, (f, )) for f in dest_garbage]
    async_tasks = [ ]
    invalid_image_names = set()
    if in_place:
        # Важно: удалить лишние файлы нужно в первую очередь, т. к. на их место
        # могут быть записаны новые.
        tasks += [(Task.REMOVE, (f, )) for f in src_garbage]
        ignored = 0
        copy_task = Task.MOVE
    else:
        ignored = len(src_garbage)
        copy_task = Task.COPY

    for ftype, src, dest in files:
        if ftype == FType.SCRIPT:
            # .rpy-скрипты.
            if cfg["_backup_style"] != BackupStyle.NONE:
                # Перемещаем файл в резервную копию.
                assert in_place
                if cfg["_backup_style"] == BackupStyle.NEARBY:
                    # Вписываем в расширение символ подчеркивания.
                    stem, ext = os.path.splitext(dest)
                    backup = "%s._%s" % (stem, ext[1:])
                elif cfg["_backup_style"] == BackupStyle.SEPARATE:
                    backup = os.path.join(cfg["_backup_location"], os.path.basename(dest))
                else:
                    assert False
                tasks.append((Task.MOVE, (src, backup)))
                if not cfg["dry_run"]:
                    # При "dry_run" мы, очевидно, не сможем открыть `backup` на чтение.
                    src = backup

            tasks.append((Task.SCRIPT, (src, dest, invalid_image_names)))
            # При работе "in_place" удаляем исходный файл.
            if in_place and src != dest and cfg["_backup_style"] == BackupStyle.NONE:
                tasks.append((Task.REMOVE, (src, )))
        elif not in_place and not is_newer(src, dest):
            # Не переделываем бесполезную тяжелую работу, если мы запущены повторно.
            ignored += 1
        elif ftype == FType.IMAGE and images_enabled:
            # Картинки.
            async_tasks.append((Task.IMAGE, (src, dest, in_place and src != dest)))
        elif src == dest:
            # Файлы, оставляемые на месте и без изменений.
            ignored += 1
        elif ftype == FType.FOREIGN:
            # Дополнительные файлы, добавляемые в мод.
            tasks.append((Task.COPY, (src, dest)))
        else:
            # Музыка, видео и прочие файлы: просто копируем/перемещаем.
            tasks.append((copy_task, (src, dest)))

    return tasks, async_tasks, ignored, invalid_image_names


# Выполнение задач.

def make_dir_structure(paths):
    created = set()
    for p in paths:
        for m in re.finditer(r"[/\\]", p):
            dir_path = p[:m.start()]
            if dir_path not in created:
                created.add(dir_path)
                with suppress_os_error(errno.EEXIST):
                    os.mkdir(dir_path)


def process_copy(stats, src, dest):
    log("Copying '%s' -> '%s'." % (src, dest), stdout=False)
    if not cfg["dry_run"]:
        shutil.copy2(src, dest)
    stats.files_copied += 1


def process_move(stats, src, dest):
    log("Moving '%s' -> '%s'." % (src, dest), stdout=False)
    if not cfg["dry_run"]:
        os.rename(src, dest)
    stats.files_moved += 1


def process_remove(stats, f):
    log("Deleting '%s'." % f, stdout=False)
    if not cfg["dry_run"]:
        os.remove(f)
    stats.files_deleted += 1


def format_paths(src, dest):
    return "'%s'" % src if src == dest else "'%s' -> '%s'" % (src, dest)


def rewrite_path_in_script(m):
    i = m.lastindex
    return cfg["_path_rewrite_repls"][i - 1] + m.group(i)


class CoordRescaler:
    def _replace_number(self, m):
        value = int(m.group())
        if value >= 10:
            # Если все "координаты" меньше 10, то, возможно, это и не координаты вовсе. Лучше не
            # будем их трогать. Даже если такое предположение ошибочно, особого вреда не нанесет.
            self._ok = True
        # Python >=3,<3.5 не поддерживает %-форматирование байтовых строк.
        return ("%.0f" % (value * SCALING_FACTOR)).encode("ascii")

    def _replace_code_fragment(self, m):
        m0 = m.group()
        if m0.startswith(b"color"):
            return m0 # Не нужно "масштабировать" цвета.
        if m0.startswith(b"size"):
            m1 = m.group(1)
            if m1 and int(m1) <= 20:
                return m0 # Не нужно делать совсем уж крошечный шрифт.
        self._ok = False
        result = NUMBER_RE.sub(self._replace_number, m0)
        return result if self._ok else m0

    def process_line(self, line):
        # Если видим наш магический комментарий, значит, строка уже обработана. Повторно ее
        # не трогаем. Наличие же `colors` означает, что дальше идут кортежи цветов.
        if b"colors" in line or b"    #m@d" in line or b"    #modded: " in line:
            return line
        return COORD_RE.sub(self._replace_code_fragment, line)


def process_rpy(stats, src, dest, invalid_image_names):
    log("Processing %s." % format_paths(src, dest), stdout=False)

    result = BytesIO()
    nl = os.linesep.encode("utf-8")
    long_comments = cfg["_comments_style"] == CommentsStyle.LONG
    if cfg["_comments_style"] == CommentsStyle.SHORT:
        comment_suffix = b"    #m@d" + nl
    else:
        comment_suffix = nl

    line_num = 0
    rewrite_paths = cfg["_path_rewrite_regex"].sub if cfg["path_rewrite_rules"] else lambda _, x: x
    rescale_coords = CoordRescaler().process_line if cfg["rescale_coordinates"] else lambda x: x
    with open(src, "rb") as f:
        for initial_line in f:
            line_num += 1
            line = rewrite_paths(rewrite_path_in_script, initial_line)
            new_line = rescale_coords(line)
            # Ищем невалидные определения изображений.
            m = IMAGE_RE.search(new_line)
            if m is not None:
                invalid_image_names.add(m.group(1))

            if new_line != initial_line:
                stats.lines_modified += 1
                # Логируем изменения.
                log("%d. %s    <= %s" % (
                    line_num,
                    new_line.decode("utf-8-sig", errors="replace").strip(),
                    initial_line.decode("utf-8-sig", errors="replace").strip(),
                ), stdout=False)
            # Пишем строчку - измененную или нет.
            result.write(new_line.rstrip(b"\r\n"))
            if new_line == line:
                # Координаты не менялись - дописываем перевод строки, и на этом всё.
                result.write(nl)
            elif long_comments:
                # Дописываем к строке комментарий.
                result.write(b"    #modded: ")
                result.write(line.strip()) # Старая строка.
                result.write(nl)
            else:
                # Дописываем короткий комментарий или просто перевод строки.
                result.write(comment_suffix)

    if not cfg["dry_run"]:
        # Пишем результат в файл.
        with open(dest, "wb") as f:
            f.write(result.getvalue())
            f.write(SCRIPT_POSTFIX)

    log("", stdout=False)
    stats.scripts_processed += 1


def process_image(stats, src, dest, delete_src):
    try:
        img = Image.open(src)
        width, height = img.size
        new_width  = int(round(width  * SCALING_FACTOR))
        new_height = int(round(height * SCALING_FACTOR))
    except Exception:
        log("While opening '%s':" % src, stdout=False)
        raise

    log("Resizing %s: (%d,%d)->(%d,%d)." % (
        format_paths(src, dest), width, height, new_width, new_height,
    ), stdout=False)

    if not cfg["dry_run"]:
        img.resize((new_width, new_height), Image.LANCZOS).save(dest)

    stats.images_processed += 1
    if delete_src:
        # Удаляем здесь, а не отдельной задачей, потому что, во-первых, обработка изображений
        # асинхронна, а во-вторых, так экономится место на диске во время работы.
        assert src != dest
        process_remove(stats, src)


class DummyProgressBar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def make_thread_safe(self):
        pass

    tick = make_thread_safe


class ProgressBar:
    def __init__(self, goal, stream):
        self._completed = 0
        self._goal = goal
        self._last_pos = 0
        self._stream = stream
        self._lock = DummyProgressBar() # Ничего не делает в `__enter__` и `__exit__`.

    def make_thread_safe(self):
        self._lock = threading.Lock() # `__enter__` и `__exit__` вызывают `acquire` и `release`.

    def __enter__(self):
        if self._goal > 0:
            self._stream.write("[{0: >77}]{0:\b>78}".format(""))
        else:
            self._stream.write("[{:=>77}]\b".format(""))
        self._stream.flush()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stream.write("\n")

    def tick(self):
        with self._lock:
            if self._completed >= self._goal:
                return
            self._completed += 1
            pos = (self._completed * 77 + (self._goal >> 1)) // self._goal
            assert 0 <= pos <= 77
            last_pos = self._last_pos
            if pos <= last_pos:
                return
            self._last_pos = pos
        # Синхронизировать запись в поток нет необходимости.
        self._stream.write("=" * (pos - last_pos))
        self._stream.flush()


def create_progress_bar(goal):
    return ProgressBar(goal, sys.stdout) if sys.stdout.isatty() else DummyProgressBar()


@contextlib.contextmanager
def handle_failures(stats):
    try:
        yield
    except Exception:
        log("FAILED:\n" + traceback.format_exc(), stdout=False)
        stats.failures += 1


def process_tasks_threaded(q_in, q_out, bar):
    stats = Stats()
    try:
        while True:
            task, args = q_in.get_nowait() # Берем входные данные из очереди.
            if task is None: # Аварийное завершение.
                break
            with handle_failures(stats):
                assert task == Task.IMAGE
                process_image(stats, *args)
            bar.tick()
    except queue.Empty:
        pass
    finally:
        q_out.put(stats) # Отправляем сводку.


def execute_tasks(tasks, async_tasks):
    # Определяем, во сколько потоков мы можем работать.
    if threading is None:
        threads_num = 1
    else:
        try:
            threads_num = multiprocessing.cpu_count()
        except NotImplementedError:
            threads_num = 1
    if threads_num <= 1:
        # Процессор одноядерный, либо у нас ущербная сборка Питона без поддержки потоков.
        tasks += async_tasks
        async_tasks = [ ]

    funcs = {
        Task.COPY:   process_copy,
        Task.MOVE:   process_move,
        Task.REMOVE: process_remove,
        Task.SCRIPT: process_rpy,
        Task.IMAGE:  process_image,
    }
    stats = Stats()
    with create_progress_bar(len(tasks) + len(async_tasks)) as bar:
        # Важно: сначала выполняем синхронные задачи.
        for task, args in tasks:
            with handle_failures(stats):
                funcs[task](stats, *args)
            bar.tick()

        if async_tasks:
            q_in = queue.Queue()
            q_out = queue.LifoQueue() # LIFO - чтобы можно было послать приоритетное сообщение.
            bar.make_thread_safe()
            # Важно: кладем задачи в очередь до запуска потоков.
            for entry in reversed(async_tasks):
                q_out.put(entry)

            threads = [ ]
            try:
                # Запускаем выполнение.
                for _ in range(threads_num):
                    th = threading.Thread(
                        target=process_tasks_threaded,
                        args=(q_out, q_in, bar),
                    )
                    threads.append(th)
                    th.start()
                # Ждем завершения.
                for th in threads:
                    # Если процессу придет сигнал, он будет отложен до возврата из `.join`.
                    # (В частности, это означает, что нас будет невозможно прибить по ^C.)
                    # Поэтому раз в секунду забираем управление.
                    while th.is_alive():
                        th.join(1)
                    stats += q_in.get_nowait() # Собираем результат.
            except BaseException:
                # Даем потокам команду прекратить работу.
                for _ in range(threads_num):
                    q_out.put((None, None))
                for th in threads:
                    th.join()
                raise

    return stats


def replace_image_names_in_file(filename, regex, replacer):
    stats = Stats()
    log("\nFixing image names in '%s'." % filename, stdout=False)
    result = BytesIO()
    line_num = 0
    modified = False
    with open(filename, "rb") as f:
        for line in f:
            line_num += 1
            line, changes = regex.subn(replacer, line)
            result.write(line)
            if changes > 0:
                modified = True
                stats.lines_modified += 1
                log("%d. %s" % (
                    line_num,
                    line.decode("utf-8-sig", errors="replace").strip(),
                ), stdout=False)

    if modified and not cfg["dry_run"]:
        with open(filename, "wb") as f:
            f.write(result.getvalue())

    return stats


def process_invalid_image_names(tasks, invalid_image_names):
    # Эта функция вызывается после первичной обработки всех скриптов, потому что ей нужно знать
    # все объявления image во всех файлах.
    stats = Stats()
    # Заменяем первую цифру прописью.
    replacements = {s: DIGIT_NAMES[s[:1]] + s[1:] for s in invalid_image_names}
    replacer = lambda m: replacements[m.group()]
    regex = re.compile(br"\b(?:" + b"|".join(map(re.escape, invalid_image_names)) + br")(?!\w)")
    i = 0 if cfg["dry_run"] else 1 # src if cfg["dry_run"] else dest
    for task, args in tasks:
        if task == Task.SCRIPT:
            with handle_failures(stats):
                stats += replace_image_names_in_file(args[i], regex, replacer)
    return stats


def remove_empty_dirs(root):
    for path, _, files in os.walk(root, topdown=False):
        # Нет смысла пытаться удалить папку, если в ней есть файлы.
        if not files:
            # Мы не проверяем `dirs` на пустоту, поскольку мы могли их стереть только что.
            # Просто пытаемся удалить себя наудачу.
            with suppress_os_error(errno.ENOTEMPTY):
                os.rmdir(path)


def run():
    stats = Stats()

    # Обрабатываем конфиг.
    log(pprint.pformat(cfg) + "\n")
    process_config()

    if cfg["dry_run"]:
        log("DRY RUN: Nothing is actually being performed.")

    old_real_root = cfg["src_path"]
    new_real_root = old_real_root if cfg["in_place"] else cfg["dest_path"]
    # Составляем список файлов мода.
    files, src_garbage, dest_garbage, auto_renames = collect_files(old_real_root, new_real_root)
    build_path_rewrite_regex(auto_renames)
    # Создаем задачи.
    tasks, async_tasks, ignored, invalid_images = generate_tasks(files, src_garbage, dest_garbage)
    stats.files_ignored += ignored

    # Выполняем созданные задачи.
    if not cfg["dry_run"]:
        make_dirs(cfg.get("_backup_location", ""))
        make_dir_structure([f for _, _, f in files])
    stats += execute_tasks(tasks, async_tasks)
    if invalid_images:
        stats += process_invalid_image_names(tasks, invalid_images)
    if not cfg["dry_run"]:
        # После перемещения/удаления файлов их директории могут остаться пустыми; удалим их.
        remove_empty_dirs(new_real_root)
        # Если работаем "in_place", переименовываем папку с модом.
        if cfg["in_place"] and cfg["dest_path"]:
            try:
                make_dirs(os.path.dirname(cfg["dest_path"].rstrip("/\\")))
                os.rename(old_real_root, cfg["dest_path"])
            except OSError as e:
                # Ловим исключение, чтобы не потерять накопленную статистику.
                log("FAILED: Cannot rename the mod directory: %s." % e)
                stats.failures += 1

    return stats


def main():
    global log_file, cfg

    args = parse_args()
    if not args.keep_cwd:
        os.chdir(os.path.dirname(sys.argv[0]) or os.path.curdir)
    status = 0
    make_dirs(os.path.dirname(args.log))
    with io.open(args.log, "w", encoding="utf-8") as log_file:
        start_time = time.time()
        try:
            log("ESTool v%s\n" % VERSION)
            cfg = read_config(args)
            stats = run()
        except Exception:
            log(traceback.format_exc())
            status = 1
            stats = Stats()
        end_time = time.time()

        summary = [ ]
        if stats.scripts_processed != 0:
            summary.append("Modified {0.lines_modified} lines in {0.scripts_processed} scripts.")
        if stats.images_processed != 0:
            summary.append("Resized {0.images_processed} images.")
        if stats.files_copied != 0:
            summary.append("Copied {0.files_copied} files.")
        if stats.files_moved != 0:
            summary.append("Moved {0.files_moved} files.")
        if stats.files_deleted != 0:
            summary.append("Deleted {0.files_deleted} files.")
        if stats.files_ignored != 0:
            summary.append("Ignored {0.files_ignored} files.")
        if stats.failures != 0:
            summary.append("{0.failures} FAILURES.")
            status = 1

        log("\nFinished in %dm %.0fs." % divmod(end_time - start_time, 60))
        if summary:
            log("\n".join(summary).format(stats))

    sys.exit(status)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        if sys.platform.startswith("win") and sys.stdin.isatty() and sys.stdout.isatty():
            input("\nPress Enter to quit.")
        raise