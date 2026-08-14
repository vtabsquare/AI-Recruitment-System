def extract_plain_email(text):
    if not text:
        return ""

    text = str(text)

    at_position = text.find("@")

    if at_position == -1:
        return ""

    start = at_position - 1

    while start >= 0:
        c = text[start]

        if c.isalnum() or c in "._%+-":
            start -= 1
        else:
            break

    start += 1

    end = at_position + 1

    while end < len(text):
        c = text[end]

        if c.isalnum() or c in ".-_":
            end += 1
        else:
            break

    return text[start:end].lower()


def clean_email(value):
    return extract_plain_email(value)
