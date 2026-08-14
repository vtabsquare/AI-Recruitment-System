import re


def clean_reply(email_body):
    """
    Extract only the candidate's latest reply.

    Removes:
    - Gmail quoted replies
    - Outlook quoted replies
    - Lines beginning with >
    - Original Message sections
    - Common email separators
    - Empty lines at the beginning/end
    """

    if not email_body:
        return ""

    text = str(email_body).replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    lines = text.split("\n")

    cleaned = []

    i = 0

    while i < len(lines):

        line = lines[i].strip()

        # ----------------------------------------------------
        # Stop at Gmail quoted reply header
        #
        # Handles formats such as:
        #
        # On Sat, 8 Aug 2026, 4:46 pm VTAB Square Recruitment,
        # <email@example.com> wrote:
        #
        # and also when everything is on one line.
        # ----------------------------------------------------

        if line.startswith("On "):

            remaining_text = "\n".join(
                lines[i:i + 4]
            )

            if re.search(
                r"\bwrote\s*:",
                remaining_text,
                re.IGNORECASE
            ):

                break

        # ----------------------------------------------------
        # Outlook quoted message
        # ----------------------------------------------------

        if line.lower().startswith("from:"):

            break

        # ----------------------------------------------------
        # Original Message separator
        # ----------------------------------------------------

        if "original message" in line.lower():

            break

        # ----------------------------------------------------
        # Common email separator
        # ----------------------------------------------------

        if line.startswith(
            "________________________________"
        ):

            break

        # ----------------------------------------------------
        # Gmail quoted lines
        # ----------------------------------------------------

        if line.startswith(">"):

            i += 1
            continue

        # ----------------------------------------------------
        # Normal candidate text
        # ----------------------------------------------------

        cleaned.append(
            lines[i]
        )

        i += 1

    # --------------------------------------------------------
    # Clean excessive blank lines
    # --------------------------------------------------------

    result = "\n".join(
        cleaned
    ).strip()

    # Remove repeated blank lines
    result = re.sub(
        r"\n{3,}",
        "\n\n",
        result
    )

    return result.strip()