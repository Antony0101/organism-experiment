"""A focused multiline Python editor widget implemented directly with Pygame."""

from __future__ import annotations

import io
import keyword
import tokenize
from dataclasses import dataclass

import pygame

from ...game.entity_projects.model import BehaviorDiagnostic


@dataclass(frozen=True, slots=True)
class CodeEditorAction:
    kind: str


class PythonCodeEditor:
    """Source editor with selection, history, highlighting, find, and diagnostics."""

    COLORS = {
        "background": (20, 23, 29),
        "gutter": (27, 31, 39),
        "text": (224, 229, 235),
        "keyword": (204, 138, 255),
        "string": (164, 214, 126),
        "number": (242, 184, 110),
        "comment": (112, 128, 144),
        "operator": (111, 198, 226),
        "selection": (48, 92, 128),
        "current_line": (27, 33, 42),
        "cursor": (246, 248, 250),
        "line_number": (105, 118, 133),
        "error": (239, 104, 104),
    }

    def __init__(self, rect: pygame.Rect, text: str = "") -> None:
        self.rect = pygame.Rect(rect)
        self.font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 15)
        self.line_height = self.font.get_linesize()
        self.char_width = max(1, self.font.size("M")[0])
        self.gutter_width = 58
        self.text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.cursor = len(self.text)
        self.anchor = self.cursor
        self.scroll_line = 0
        self.scroll_column = 0
        self.focused = False
        self.dragging = False
        self.diagnostics: tuple[BehaviorDiagnostic, ...] = ()
        self._undo: list[tuple[str, int, int]] = []
        self._redo: list[tuple[str, int, int]] = []
        self.find_active = False
        self.find_query = ""
        self._last_find = -1
        self._blink_started = pygame.time.get_ticks()

    @property
    def dirty_selection(self) -> tuple[int, int]:
        return (min(self.cursor, self.anchor), max(self.cursor, self.anchor))

    def resize(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)
        self._ensure_cursor_visible()

    def set_text(self, text: str, *, clear_history: bool = True) -> None:
        self.text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.cursor = min(len(self.text), self.cursor)
        self.anchor = self.cursor
        if clear_history:
            self._undo.clear()
            self._redo.clear()
        self._ensure_cursor_visible()

    def set_diagnostics(self, diagnostics: tuple[BehaviorDiagnostic, ...]) -> None:
        self.diagnostics = diagnostics

    def _remember(self) -> None:
        state = (self.text, self.cursor, self.anchor)
        if not self._undo or self._undo[-1] != state:
            self._undo.append(state)
            del self._undo[:-200]
        self._redo.clear()

    def _restore(self, source: list[tuple[str, int, int]], destination: list[tuple[str, int, int]]) -> None:
        if not source:
            return
        destination.append((self.text, self.cursor, self.anchor))
        self.text, self.cursor, self.anchor = source.pop()
        self._ensure_cursor_visible()

    def _line_column(self, index: int | None = None) -> tuple[int, int]:
        position = self.cursor if index is None else max(0, min(len(self.text), index))
        line = self.text.count("\n", 0, position)
        start = self.text.rfind("\n", 0, position) + 1
        return line, position - start

    def _index(self, line: int, column: int) -> int:
        lines = self.text.split("\n")
        line = max(0, min(len(lines) - 1, line))
        column = max(0, min(len(lines[line]), column))
        return sum(len(item) + 1 for item in lines[:line]) + column

    def _visible_line_count(self) -> int:
        return max(1, (self.rect.height - 8) // self.line_height)

    def _ensure_cursor_visible(self) -> None:
        line, column = self._line_column()
        visible = self._visible_line_count()
        if line < self.scroll_line:
            self.scroll_line = line
        elif line >= self.scroll_line + visible:
            self.scroll_line = line - visible + 1
        text_columns = max(1, (self.rect.width - self.gutter_width - 18) // self.char_width)
        if column < self.scroll_column:
            self.scroll_column = column
        elif column >= self.scroll_column + text_columns:
            self.scroll_column = column - text_columns + 1

    def _move(self, index: int, selecting: bool) -> None:
        self.cursor = max(0, min(len(self.text), index))
        if not selecting:
            self.anchor = self.cursor
        self._blink_started = pygame.time.get_ticks()
        self._ensure_cursor_visible()

    def _replace_selection(self, value: str) -> None:
        self._remember()
        start, end = self.dirty_selection
        self.text = self.text[:start] + value + self.text[end:]
        self.cursor = start + len(value)
        self.anchor = self.cursor
        self._ensure_cursor_visible()

    def _copy(self) -> None:
        start, end = self.dirty_selection
        if start == end:
            return
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            pygame.scrap.put(pygame.SCRAP_TEXT, self.text[start:end].encode("utf-8") + b"\x00")
        except pygame.error:
            pass

    def _paste(self) -> None:
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        except pygame.error:
            raw = None
        if raw:
            self._replace_selection(raw.rstrip(b"\x00").decode("utf-8", errors="replace"))

    def _indent_selection(self, outdent: bool) -> None:
        start, end = self.dirty_selection
        start_line, _ = self._line_column(start)
        end_line, end_column = self._line_column(end)
        if end_column == 0 and end > start:
            end_line -= 1
        lines = self.text.split("\n")
        self._remember()
        for line_number in range(start_line, end_line + 1):
            if outdent:
                if lines[line_number].startswith("    "):
                    lines[line_number] = lines[line_number][4:]
                elif lines[line_number].startswith("\t"):
                    lines[line_number] = lines[line_number][1:]
            else:
                lines[line_number] = "    " + lines[line_number]
        self.text = "\n".join(lines)
        new_start = self._index(start_line, 0)
        new_end = self._index(end_line, len(lines[end_line]))
        self.anchor, self.cursor = new_start, new_end
        self._ensure_cursor_visible()

    def _newline(self) -> None:
        line, _ = self._line_column()
        current = self.text.split("\n")[line]
        indentation = current[: len(current) - len(current.lstrip(" \t"))]
        before = self.text[: self.cursor].rstrip()
        if before.endswith(":"):
            indentation += "    "
        self._replace_selection("\n" + indentation)

    def _find_next(self) -> None:
        if not self.find_query:
            return
        start = self.cursor if self._last_find < 0 else self._last_find + 1
        found = self.text.casefold().find(self.find_query.casefold(), start)
        if found < 0:
            found = self.text.casefold().find(self.find_query.casefold(), 0, start)
        if found >= 0:
            self.anchor = found
            self.cursor = found + len(self.find_query)
            self._last_find = found
            self._ensure_cursor_visible()

    def _cursor_from_position(self, position: tuple[int, int]) -> int:
        local_x = position[0] - self.rect.x - self.gutter_width - 6
        local_y = position[1] - self.rect.y - 4
        line = self.scroll_line + max(0, local_y // self.line_height)
        column = self.scroll_column + max(0, round(local_x / self.char_width))
        return self._index(line, column)

    def handle_event(self, event: pygame.event.Event) -> CodeEditorAction | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            if self.focused:
                new_cursor = self._cursor_from_position(event.pos)
                if not pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self.anchor = new_cursor
                self.cursor = new_cursor
                self.dragging = True
                self._ensure_cursor_visible()
            return None
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.cursor = self._cursor_from_position(event.pos)
            self._ensure_cursor_visible()
        elif event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll_line = max(0, self.scroll_line - event.y * 3)
        if not self.focused:
            return None

        if event.type == pygame.TEXTINPUT:
            if self.find_active:
                self.find_query += event.text
                self._last_find = -1
            else:
                self._replace_selection(event.text)
            return None
        if event.type != pygame.KEYDOWN:
            return None

        ctrl = bool(event.mod & pygame.KMOD_CTRL)
        shift = bool(event.mod & pygame.KMOD_SHIFT)
        if ctrl and event.key == pygame.K_s:
            return CodeEditorAction("save")
        if event.key == pygame.K_F5:
            return CodeEditorAction("apply")
        if ctrl and event.key == pygame.K_f:
            self.find_active = True
            self.find_query = ""
            self._last_find = -1
            return None
        if self.find_active:
            if event.key == pygame.K_ESCAPE:
                self.find_active = False
            elif event.key == pygame.K_BACKSPACE:
                self.find_query = self.find_query[:-1]
                self._last_find = -1
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._find_next()
            return None
        if ctrl and event.key == pygame.K_a:
            self.anchor = 0
            self.cursor = len(self.text)
        elif ctrl and event.key == pygame.K_c:
            self._copy()
        elif ctrl and event.key == pygame.K_x:
            self._copy()
            if self.cursor != self.anchor:
                self._replace_selection("")
        elif ctrl and event.key == pygame.K_v:
            self._paste()
        elif ctrl and event.key == pygame.K_z:
            self._restore(self._undo, self._redo)
        elif ctrl and event.key == pygame.K_y:
            self._restore(self._redo, self._undo)
        elif event.key == pygame.K_BACKSPACE:
            if self.cursor != self.anchor:
                self._replace_selection("")
            elif self.cursor:
                self.anchor = self.cursor - 1
                self._replace_selection("")
        elif event.key == pygame.K_DELETE:
            if self.cursor != self.anchor:
                self._replace_selection("")
            elif self.cursor < len(self.text):
                self.anchor = self.cursor + 1
                self._replace_selection("")
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._newline()
        elif event.key == pygame.K_TAB:
            if self.cursor != self.anchor:
                self._indent_selection(shift)
            elif shift:
                line, column = self._line_column()
                remove = min(4, len(self.text[self._index(line, 0) : self.cursor]) - len(self.text[self._index(line, 0) : self.cursor].lstrip(" ")))
                if remove:
                    self.anchor = self.cursor - remove
                    self._replace_selection("")
            else:
                self._replace_selection("    ")
        elif event.key == pygame.K_LEFT:
            self._move(self.cursor - 1, shift)
        elif event.key == pygame.K_RIGHT:
            self._move(self.cursor + 1, shift)
        elif event.key in (pygame.K_UP, pygame.K_DOWN):
            line, column = self._line_column()
            self._move(self._index(line + (-1 if event.key == pygame.K_UP else 1), column), shift)
        elif event.key == pygame.K_HOME:
            line, _ = self._line_column()
            self._move(self._index(line, 0), shift)
        elif event.key == pygame.K_END:
            line, _ = self._line_column()
            lines = self.text.split("\n")
            self._move(self._index(line, len(lines[line])), shift)
        elif event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            line, column = self._line_column()
            delta = self._visible_line_count() * (-1 if event.key == pygame.K_PAGEUP else 1)
            self._move(self._index(line + delta, column), shift)
        elif event.key == pygame.K_ESCAPE:
            self.anchor = self.cursor
        return None

    def _highlight_spans(self) -> dict[int, list[tuple[int, int, tuple[int, int, int]]]]:
        spans: dict[int, list[tuple[int, int, tuple[int, int, int]]]] = {}
        try:
            tokens = tokenize.generate_tokens(io.StringIO(self.text).readline)
            for token in tokens:
                color = self.COLORS["text"]
                if token.type == tokenize.NAME and keyword.iskeyword(token.string):
                    color = self.COLORS["keyword"]
                elif token.type == tokenize.STRING:
                    color = self.COLORS["string"]
                elif token.type == tokenize.NUMBER:
                    color = self.COLORS["number"]
                elif token.type == tokenize.COMMENT:
                    color = self.COLORS["comment"]
                elif token.type == tokenize.OP:
                    color = self.COLORS["operator"]
                else:
                    continue
                if token.start[0] == token.end[0]:
                    spans.setdefault(token.start[0] - 1, []).append(
                        (token.start[1], token.end[1], color)
                    )
        except (tokenize.TokenError, IndentationError):
            pass
        return spans

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.COLORS["background"], self.rect)
        gutter = pygame.Rect(self.rect.x, self.rect.y, self.gutter_width, self.rect.height)
        pygame.draw.rect(surface, self.COLORS["gutter"], gutter)
        pygame.draw.rect(surface, (71, 82, 96), self.rect, width=1)
        clip_before = surface.get_clip()
        surface.set_clip(self.rect)
        lines = self.text.split("\n")
        cursor_line, cursor_column = self._line_column()
        visible_count = self._visible_line_count()
        selection_start, selection_end = self.dirty_selection
        diagnostics_by_line = {item.line - 1: item for item in self.diagnostics}
        spans = self._highlight_spans()
        for line_number in range(
            self.scroll_line, min(len(lines), self.scroll_line + visible_count + 1)
        ):
            y = self.rect.y + 4 + (line_number - self.scroll_line) * self.line_height
            if line_number == cursor_line:
                pygame.draw.rect(
                    surface,
                    self.COLORS["current_line"],
                    (self.rect.x + self.gutter_width, y, self.rect.width - self.gutter_width, self.line_height),
                )
            rendered_number = self.small_font.render(
                str(line_number + 1), True, self.COLORS["line_number"]
            )
            surface.blit(
                rendered_number,
                (self.rect.x + self.gutter_width - rendered_number.get_width() - 8, y + 2),
            )
            if line_number in diagnostics_by_line:
                pygame.draw.circle(surface, self.COLORS["error"], (self.rect.x + 8, y + self.line_height // 2), 4)

            line_start = self._index(line_number, 0)
            line_end = line_start + len(lines[line_number])
            selected_start = max(selection_start, line_start)
            selected_end = min(selection_end, line_end)
            if selected_start < selected_end:
                start_col = selected_start - line_start - self.scroll_column
                end_col = selected_end - line_start - self.scroll_column
                pygame.draw.rect(
                    surface,
                    self.COLORS["selection"],
                    (
                        self.rect.x + self.gutter_width + 6 + start_col * self.char_width,
                        y,
                        (end_col - start_col) * self.char_width,
                        self.line_height,
                    ),
                )

            visible_text = lines[line_number][self.scroll_column :]
            x = self.rect.x + self.gutter_width + 6
            colors = [self.COLORS["text"]] * len(visible_text)
            for start, end, color in spans.get(line_number, ()):
                for index in range(max(start, self.scroll_column), min(end, len(lines[line_number]))):
                    colors[index - self.scroll_column] = color
            run_start = 0
            while run_start < len(visible_text):
                run_end = run_start + 1
                while run_end < len(visible_text) and colors[run_end] == colors[run_start]:
                    run_end += 1
                segment = visible_text[run_start:run_end]
                rendered = self.font.render(segment.replace("\t", "    "), True, colors[run_start])
                surface.blit(rendered, (x + run_start * self.char_width, y))
                run_start = run_end

        if self.focused and (pygame.time.get_ticks() - self._blink_started) % 1000 < 550:
            x = (
                self.rect.x
                + self.gutter_width
                + 6
                + (cursor_column - self.scroll_column) * self.char_width
            )
            y = self.rect.y + 4 + (cursor_line - self.scroll_line) * self.line_height
            pygame.draw.line(surface, self.COLORS["cursor"], (x, y), (x, y + self.line_height - 2), 2)

        if self.find_active:
            find_rect = pygame.Rect(self.rect.right - 330, self.rect.y + 8, 310, 32)
            pygame.draw.rect(surface, (38, 44, 54), find_rect, border_radius=5)
            pygame.draw.rect(surface, (98, 116, 134), find_rect, width=1, border_radius=5)
            label = self.small_font.render(
                f"Find: {self.find_query}", True, self.COLORS["text"]
            )
            surface.blit(label, (find_rect.x + 8, find_rect.y + 7))
        surface.set_clip(clip_before)


__all__ = ["CodeEditorAction", "PythonCodeEditor"]
