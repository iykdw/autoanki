import re

from autoanki.note_html import basic_after, basic_before, basic_between


class Cloze:
    def __init__(self, text="", back_extra=""):
        self.text = text
        self.back_extra = back_extra
        self.tags = ""
        self.regex = r"{{c[0-9+]::"

        self.before_html = basic_before
        self.between_html = basic_between
        self.after_html = basic_after

    def html(self):
        htmlified_text = (
            re.sub(self.regex, r"<span style='color: blue'>", self.text)
            .replace("}}", "</span>")
            .replace("\\(", "<mathjax>\\(")
            .replace("\\)", "\\)</mathjax>")
        )
        while (match := re.search(r"\n - (.+)\n", htmlified_text)) is not None:
            htmlified_text = htmlified_text.replace(f"{match.group(0)}", f"\n<li>{match.group(0)[4:-1]}</li>\n")

        html_text = htmlified_text.split("\n")
        for i in range(len(html_text)):
            if html_text[i].startswith("</li>"):
                html_text[i] = f"<ul>\n{html_text[i]}"
                break

        htmlified_text = "\n".join(html_text) + "</ul>"

        return f"{self.before_html}{htmlified_text}{self.between_html if self.back_extra != '' else ''}{self.back_extra if self.back_extra != '' else ''}{self.after_html}"

    def __str__(self):
        return f"# Note\nmodel: Cloze\ntags: {self.tags}\n\n## Text\n{self.text}\n\n## Back Extra\n{self.back_extra}\n\n"

    def __repr__(self):
        return self.__str__()


class Basic:
    def __init__(self, front="", back=""):
        self.front = front
        self.back = back
        self.tags = ""

        self.model = "Basic"

        self.before_html = basic_before
        self.between_html = basic_between
        self.after_html = basic_after

    def html(self):
        htmlified_front = self.front.replace("\\(", "<mathjax>\\(").replace("\\)", "\\)</mathjax>")
        htmlified_back = self.back.replace("\\(", "<mathjax>\\(").replace("\\)", "\\)</mathjax>")
        return f"{self.before_html}{htmlified_front}{self.between_html}{htmlified_back}{self.after_html}"

    def __str__(self):
        return f"# Note\nmodel: {self.model}\ntags: {self.tags}\n\n## Front\n{self.front}\n\n## Back\n{self.back}\n\n"

    def __repr__(self):
        return self.__str__()


class Basic_And_Reversed(Basic):
    def __init__(self, front="", back=""):
        super().__init__()
        self.model = "Basic (and reversed card)"
