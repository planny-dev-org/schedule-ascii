import datetime

SHIFT_DISPLAY_SEQ = "ABCDEFGHIJKLMNOPQRTSUVWXYZabcdefghijklmnopqrstuvwxyz1234567890"


class Drawer:
    """
    ASCII printer
    """

    def __init__(self, db_adapter):
        self.block_width = 30
        self.day_width = 3
        self.db_adapter = db_adapter

    def init_shift_ascii_display(self):
        """
        Set shift's table ascii_display column
        :return:
        """
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
        holiday_shift = self.db_adapter.select("shift", ["id"], "id='HOL'")
        if holiday_shift:
            self.db_adapter.update(
                "shift", f"id='{holiday_shift[0][0]}'", "ascii_display='|'"
            )
        off_shift = self.db_adapter.select("shift", ["id"], "id='OFF'")
        if off_shift:
            self.db_adapter.update(
                "shift", f"id='{off_shift[0][0]}'", "ascii_display='-'"
            )

        # find closer display using first shift id letter
        for shift in self.db_adapter.select("shift", ["id"], "ascii_display=''"):
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
        for shift in self.db_adapter.select("shift", ["id"], "ascii_display=''"):
            ascii_display = shift_display_seq.pop(0)
            self.db_adapter.update(
                "shift", f"id='{shift[0]}'", f"ascii_display='{ascii_display}'"
            )

    def draw_sep(self, size=100):
        """
        Draw a separator
        """
        print(f"{'-'*size}")

    def draw_list(self, labels):
        """
        Draw a list of labels at fixed positions
        """
        line = ""
        for label in labels:
            line += f"{label:<{self.block_width}}"
        print(f"{line}")

    def draw_indented_list(self, labels):
        """
        Same as draw_list but first position is fixed using self.block_width (larger block)
        Then, positions are fixed using self.day_width (smaller blocks)
        """
        line = f"{labels[0]:<{self.block_width}}"
        for label in labels[1:]:
            line += f"{label:<{self.day_width}}"
        print(f"{line}")

    def draw(self):
        self.draw_sep(104)

        # draw schedule
        start_day, time_span_days = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        self.draw_list(["start day", "num of days"])
        self.draw_list([start_day, time_span_days])
        self.draw_sep(104)

        # draw shifts
        self.draw_list(["shift id", "duration", "start_time", "end_time", "display"])
        for shift_data in self.db_adapter.select(
            "shift",
            [
                "id",
                "display_name",
                "ascii_display",
                "duration",
                "start_time",
                "end_time",
            ],
        ):
            shift_id, display_name, ascii_display, duration, start_time, end_time = (
                shift_data
            )
            self.draw_list(
                [
                    shift_id,
                    round(duration / 3600, 1),
                    start_time,
                    end_time,
                    ascii_display,
                ]
            )
        self.draw_sep(104)

        # draw people
        self.draw_list(
            [
                "person id",
                "act rate",
                "target (h)",
                "work (h)",
                "delta (h)",
                "holidays (h)",
                "debt (h)",
            ]
        )
        people_data = self.db_adapter.select(
            "person",
            [
                "id",
                "activity_rate",
                "night_count",
                "weekend_count",
                "target_hours",
                "holiday_hours",
                "effective_hours",
                "debt_hours",
            ],
        )
        for person_data in people_data:
            (
                person_id,
                activity_rate,
                night_count,
                weekend_count,
                target_hours,
                holiday_hours,
                effective_hours,
                debt_hours,
            ) = person_data
            self.draw_list(
                [
                    person_id,
                    activity_rate,
                    round(target_hours, 1),
                    round(effective_hours, 1),
                    round(target_hours - effective_hours, 1),
                    round(holiday_hours, 1),
                    round(debt_hours, 1),
                ]
            )
        self.draw_sep(104)

        # draw tasks
        ## days
        days = list(range(time_span_days))
        start_date = datetime.date.fromisoformat(start_day)
        is_we = []
        for day in days:
            iso_day = start_date + datetime.timedelta(days=day)
            if iso_day.weekday() in [5, 6]:
                is_we.append("X")
            else:
                is_we.append("")
        self.draw_indented_list([""] + days)
        self.draw_indented_list([""] + is_we)
        self.draw_sep(len(days) * self.day_width + self.block_width)
        ## tasks
        for person_data in people_data:
            tasks = self.db_adapter.select_person_tasks(person_data[0])  # 0: person id
            task_items = {}
            for display, day in tasks:
                task_items[day] = display
            labels = [person_data[0]]
            for day in days:
                labels.append(task_items.get(day, " "))
            self.draw_indented_list(labels)
