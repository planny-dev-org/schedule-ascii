SHIFT_DISPLAY_SEQ = "ABCDEFGHIJKLMNOPQRTSUVWXYZabcdefghijklmnopqrstuvwxyz1234567890"


class Drawer:
    """
    ASCII printer
    """

    def __init__(self, db_adapter):
        self.block_width = 40
        self.day_width = 3
        self.db_adapter = db_adapter

    def init_shift_ascii_display(self):
        shift_display_seq = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "T",
            "S",
            "U",
            "V",
            "W",
            "X",
            "Y",
            "Z",
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
            "v",
            "w",
            "x",
            "y",
            "z",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "0",
        ]
        holiday_shift = self.db_adapter.select("shift", ["id"], "id='HOL'").fetchall()
        if holiday_shift:
            self.db_adapter.update(
                "shift", f"id='{holiday_shift[0][0]}'", "ascii_display='|'"
            )
        off_shift = self.db_adapter.select("shift", ["id"], "id='OFF'").fetchall()
        if off_shift:
            self.db_adapter.update(
                "shift", f"id='{off_shift[0][0]}'", "ascii_display='-'"
            )

        # find closer display using first shift id letter
        for shift in self.db_adapter.select(
            "shift", ["id"], "ascii_display=''"
        ).fetchall():
            ascii_display = None
            char = shift[0][0]
            if char in shift_display_seq:
                ascii_display = shift_display_seq.pop(shift_display_seq.index(char))
            else:
                for method in "upper", "lower":
                    char = getattr(char, method)()
                    if char in shift_display_seq:
                        ascii_display = shift_display_seq.pop(
                            shift_display_seq.index(char)
                        )
                        break
            if ascii_display:
                self.db_adapter.update(
                    "shift", f"id='{shift[0]}'", f"ascii_display='{ascii_display}'"
                )

        # for all shifts without ascii display, assign one of the remaining display sequence items
        for shift in self.db_adapter.select(
            "shift", ["id"], "ascii_display=''"
        ).fetchall():
            ascii_display = shift_display_seq.pop(0)
            self.db_adapter.update(
                "shift", f"id='{shift[0]}'", f"ascii_display='{ascii_display}'"
            )
