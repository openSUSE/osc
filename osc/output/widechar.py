import unicodedata


def wc_width(text):
    result = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ("F", "W"):
            result += 2
        else:
            result += 1
    return result


def wc_ljust(text, width, fillchar=" "):
    text_width = wc_width(text)
    fill_width = wc_width(fillchar)

    while text_width + fill_width <= width:
        text += fillchar
        text_width += fill_width

    return text
