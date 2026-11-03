import re

from autoanki.note_html import basic_after, basic_before, basic_between


class Cloze:
    def __init__(self, text: str = "", back_extra: str = "") -> None:
        self._text: str = text
        self._back_extra: str = back_extra
        self.tags: str = ""
        self._nid: int = -1
        self.regex = r"{{c[0-9]+::"

        self.before_html = basic_before
        self.between_html = basic_between
        self.after_html = basic_after

    @property
    def nid(self) -> int:
        return self._nid

    @nid.setter
    def nid(self, value) -> None:
        if value == 0:
            raise ValueError
        self._nid = int(value)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value.strip()

    @property
    def back_extra(self) -> str:
        return self._back_extra

    @back_extra.setter
    def back_extra(self, value: str) -> None:
        self._back_extra = value.strip()

    def html(self) -> str:
        htmlified_text = re.sub(self.regex, r"<span style='color: blue'>", self.text).replace("}}", "</span>").replace("\\(", "<mathjax>\\(").replace("\\)", "\\)</mathjax>")
        while (match := re.search(r"\n - (.+)\n", htmlified_text)) is not None:
            htmlified_text = htmlified_text.replace(f"{match.group(0)}", f"\n\n<li>{match.group(0)[4:-1]}</li>\n")

        html_text = htmlified_text.split("\n")
        for i in range(len(html_text)):
            if html_text[i].startswith("</li>"):
                html_text[i] = f"<ul>\n{html_text[i]}"
                break

        htmlified_text = "\n".join(html_text) + "</ul>"

        return f"{self.before_html}{htmlified_text}{self.between_html if self.back_extra else ''}{self.back_extra if self.back_extra else ''}{self.after_html}"

    def __str__(self) -> str:
        return f"# Note\nmodel: Cloze\ntags: {self.tags}\n{f'nid: {self.nid}\n' if self.nid > 0 else ''}\n## Text\n{self.text}\n\n## Back Extra\n{self.back_extra}\n\n\n"

    def __repr__(self) -> str:
        return self.__str__()


class Basic:
    def __init__(self, front: str = "", back: str = "") -> None:
        self._front = front
        self._back = back
        self.tags = ""
        self._nid = -1

        self.model = "Basic"

        self.before_html = basic_before
        self.between_html = basic_between
        self.after_html = basic_after

    @property
    def nid(self) -> int:
        return self._nid

    @nid.setter
    def nid(self, value) -> None:
        if value == 0:
            raise ValueError
        self._nid = int(value)

    @property
    def front(self) -> str:
        return self._front

    @front.setter
    def front(self, value) -> None:
        self._front = value.strip()

    @property
    def back(self) -> str:
        return self._back

    @back.setter
    def back(self, value) -> None:
        self._back = value.strip()

    def html(self) -> str:
        htmlified_front = self.front.replace("\\(", "<mathjax>\\(").replace("\\)", "\\)</mathjax>")
        htmlified_back = self.back.replace("\\(", "<mathjax>\\(").replace("\\)", "\\)</mathjax>")
        return f"{self.before_html}{htmlified_front}{self.between_html}{htmlified_back}{self.after_html}"

    def __str__(self) -> str:
        return f"# Note\nmodel: {self.model}\ntags: {self.tags}\n{f'nid: {self.nid}\n' if self.nid > 0 else ''}\n\n## Front\n{self.front}\n\n## Back\n{self.back}\n\n\n"

    def __repr__(self) -> str:
        return self.__str__()


class BasicAndReversed(Basic):
    def __init__(self, front: str = "", back: str = "") -> None:
        super().__init__(front=front, back=back)
        self.model = "Basic (and reversed card)"
