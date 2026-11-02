import re

from autoanki.note_html import basic_after, basic_before, basic_between


class Cloze:
    def __init__(self, text: str = "", back_extra: str = "") -> None:
        self.text = text
        self.back_extra = back_extra
        self.tags = ""
        self.nid = ""
        self.regex = r"{{c[0-9]+::"

        self.before_html = basic_before
        self.between_html = basic_between
        self.after_html = basic_after

    def html(self) -> str:
        htmlified_text = (
            re
            .sub(self.regex, r"<span style='color: blue'>", self.text)
            .replace("}}", "</span>")
            .replace("\\(", "<mathjax>\\(")
            .replace("\\)", "\\)</mathjax>")
        )
        while (match := re.search(r"\n - (.+)\n", htmlified_text)) is not None:
            htmlified_text = htmlified_text.replace(
                f"{match.group(0)}", f"\n\n<li>{match.group(0)[4:-1]}</li>\n"
            )

        html_text = htmlified_text.split("\n")
        for i in range(len(html_text)):
            if html_text[i].startswith("</li>"):
                html_text[i] = f"<ul>\n{html_text[i]}"
                break

        htmlified_text = "\n".join(html_text) + "</ul>"

        return f"{self.before_html}{htmlified_text}{self.between_html if self.back_extra else ''}{self.back_extra if self.back_extra else ''}{self.after_html}"

    def __str__(self) -> str:
        return f"# Note\nmodel: Cloze\ntags: {self.tags}\n{f'nid: {self.nid}\n' if self.nid else ''}\n## Text\n{self.text}\n\n## Back Extra\n{self.back_extra}\n\n\n"

    def __repr__(self) -> str:
        return self.__str__()


class Basic:
    def __init__(self, front: str = "", back: str = "") -> None:
        self.front = front
        self.back = back
        self.tags = ""
        self.nid = ""

        self.model = "Basic"

        self.before_html = basic_before
        self.between_html = basic_between
        self.after_html = basic_after

    def html(self) -> str:
        htmlified_front = self.front.replace("\\(", "<mathjax>\\(").replace(
            "\\)", "\\)</mathjax>"
        )
        htmlified_back = self.back.replace("\\(", "<mathjax>\\(").replace(
            "\\)", "\\)</mathjax>"
        )
        return f"{self.before_html}{htmlified_front}{self.between_html}{htmlified_back}{self.after_html}"

    def __str__(self) -> str:
        return f"# Note\nmodel: {self.model}\ntags: {self.tags}\n{f'nid: {self.nid}\n' if self.nid else ''}\n\n## Front\n{self.front}\n\n## Back\n{self.back}\n\n\n"

    def __repr__(self) -> str:
        return self.__str__()


class BasicAndReversed(Basic):
    def __init__(self, front: str = "", back: str = "") -> None:
        super().__init__(front=front, back=back)
        self.model = "Basic (and reversed card)"
