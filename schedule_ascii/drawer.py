import datetime
from schedule_ascii.analytics import standard_deviation, hours_score, fairness_score

SHIFT_DISPLAY_SEQ = "ABCDEFGHIJKLMNOPQRTSUVWXYZabcdefghijklmnopqrstuvwxyz1234567890"


class BColors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class BaseDrawer:

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

    def draw_list(self, labels, block_width=None):
        """
        Draw a list of labels at fixed positions
        """
        if block_width is None:
            block_width = self.block_width
        line = ""
        for label in labels:
            line += f"{label:<{block_width}}"
        print(f"{line}")

    def draw_indented_list(self, labels, first_width=None, width=None):
        """
        Same as draw_list but first position is fixed using self.block_width (larger block)
        Then, positions are fixed using self.day_width (smaller blocks)
        """
        if first_width is None:
            first_width = self.block_width
        if width is None:
            width = self.day_width
        line = f"{labels[0][:first_width]:<{first_width}}"
        for label in labels[1:]:
            line += f"{label:<{width}}"
        print(f"{line}")

    def draw_schedule(self):
        """
        Draw schedule table
        :return:
        """

        start_day, time_span_days = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        self.draw_list(["start day", "num of days"])
        self.draw_list([start_day, time_span_days])
        self.draw_sep(104)

    def draw_shifts(self):
        """
        Draw shifts table
        :return:
        """
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

    def draw_people(self):
        """
        Draw people table
        :return:
        """
        self.draw_indented_list(
            [
                "person id",
                "act rate",
                "Tg(h)",
                "Wo(h)",
                "Diff(h)",
                "Hol(h)",
                "Deb(h)",
                "Nc",
                "Wc",
            ],
            first_width=30,
            width=15,
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
            self.draw_indented_list(
                [
                    person_id,
                    activity_rate,
                    round(target_hours, 1),
                    round(effective_hours, 1),
                    round(effective_hours - target_hours, 1),
                    round(holiday_hours, 1),
                    round(debt_hours, 1),
                    night_count,
                    weekend_count,
                ],
                first_width=30,
                width=15,
            )
        self.draw_sep(120)


class ScheduleDrawer(BaseDrawer):
    """
    Schedule ASCII printer
    """

    def __init__(self, db_adapter):
        self.block_width = 30
        self.day_width = 3
        self.db_adapter = db_adapter

    def draw(self):
        self.draw_sep(104)

        # draw schedule
        self.draw_schedule()

        # draw shifts
        self.draw_shifts()

        # draw people
        self.draw_people()

        #############
        # draw tasks
        #############
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
        start_day, time_span_days = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        # days
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
        # tasks
        for person_data in people_data:
            tasks = self.db_adapter.select_person_tasks(person_data[0])  # 0: person id
            task_items = {}
            for display, day in tasks:
                task_items[day] = display
            labels = [person_data[0]]
            for day in days:
                labels.append(task_items.get(day, " "))
            self.draw_indented_list(labels)
        self.draw_sep(120)

        #############
        # analytics
        #############
        # people hours
        legend = ["Hours", "raw", "wo extremes"]
        self.draw_indented_list(legend, first_width=15, width=10)
        raw_values = [
            (int(abs(person_data[4] - person_data[6])), int(person_data[4]))
            for person_data in people_data
        ]  # [(delta, target), ...]
        min_value = min(raw_values)
        max_value = max(raw_values)
        wo_extremes_values = [
            value for value in raw_values if value not in [min_value, max_value]
        ]
        min_wo_extremes_value = (
            min(wo_extremes_values) if wo_extremes_values else min_value
        )
        max_wo_extremes_value = (
            max(wo_extremes_values) if wo_extremes_values else max_value
        )
        self.draw_indented_list(
            ["delta min (h)", min_value[0], min_wo_extremes_value[0]],
            first_width=15,
            width=10,
        )
        self.draw_indented_list(
            [
                "delta max (h)",
                max_value[0],
                max_wo_extremes_value[0],
            ],
            first_width=15,
            width=10,
        )
        raw_std = standard_deviation([raw_value[0] for raw_value in raw_values])
        wo_extremes_std = standard_deviation(
            [wo_extremes_value[0] for wo_extremes_value in wo_extremes_values]
        )
        self.draw_indented_list(
            ["std dev (h)", raw_std, wo_extremes_std], first_width=15, width=10
        )
        raw_hours_total_delta, raw_hours_total_target, raw_hours_score = hours_score(
            raw_values
        )
        wo_hours_total_delta, wo_hours_total_target, wo_hours_score = hours_score(
            wo_extremes_values
        )
        self.draw_indented_list(
            [
                "total dev (h)",
                f"{int(raw_hours_total_delta)}",
                f"{int(wo_hours_total_delta)}",
            ],
            first_width=15,
            width=10,
        )
        self.draw_indented_list(
            [
                "total tgt (h)",
                f"{int(raw_hours_total_target)}",
                f"{int(wo_hours_total_target)}",
            ],
            first_width=15,
            width=10,
        )
        self.draw_indented_list(
            [
                "score (%)",
                f"{int(raw_hours_score)}%",
                f"{int(wo_hours_score)}%",
            ],
            first_width=15,
            width=10,
        )
        self.draw_sep(120)

        # fairnesses
        for index in [2, 3]:  # 2: night count, 3: weekend count
            label = "Night count" if index == 2 else "Weekend count"
            legend = [label, "raw", "wo extremes"]
            self.draw_indented_list(legend, first_width=15, width=10)
            raw_values = [person_data[index] for person_data in people_data]
            min_value = min(raw_values)
            max_value = max(raw_values)
            wo_extremes_values = [
                value for value in raw_values if value not in [min_value, max_value]
            ]
            min_wo_extremes_value = (
                min(wo_extremes_values) if wo_extremes_values else min_value
            )
            max_wo_extremes_value = (
                max(wo_extremes_values) if wo_extremes_values else max_value
            )
            self.draw_indented_list(
                ["min", min_value, min_wo_extremes_value], first_width=15, width=10
            )
            self.draw_indented_list(
                [
                    "max",
                    max_value,
                    max_wo_extremes_value,
                ],
                first_width=15,
                width=10,
            )
            raw_std = standard_deviation(raw_values)
            wo_extremes_std = standard_deviation(wo_extremes_values)
            self.draw_indented_list(
                ["std dev", raw_std, wo_extremes_std], first_width=15, width=10
            )

            raw_fairness_delta_total, raw_fairness_score = fairness_score(raw_values)
            wo_fairness_delta_total, wo_fairness_score = fairness_score(
                wo_extremes_values
            )
            self.draw_indented_list(
                [
                    "total dev",
                    f"{int(raw_fairness_delta_total)}",
                    f"{int(wo_fairness_delta_total)}",
                ],
                first_width=15,
                width=10,
            )

            self.draw_indented_list(
                [
                    "score (%)",
                    f"{int(raw_fairness_score)}%",
                    f"{int(wo_fairness_score)}%",
                ],
                first_width=15,
                width=10,
            )

            self.draw_sep(120)


class CapacityDrawer(BaseDrawer):
    """
    Draw schedule capacity.
    For each shift for each day, draw 1 line with required minimal coverage and 1 line with count of available people
    """

    @classmethod
    def colorize(cls, needs_line, capacity_line):
        """
        Given 2 lists of values, convert to colorized strings based on values delta
        need value = capactity value => yellow
        need value > capactity value => red
        """
        if len(needs_line) != len(capacity_line):
            raise ValueError("needs and capacity lines must have same length")
        for i in range(len(needs_line)):
            need_value = needs_line[i]
            capacity_value = capacity_line[i]
            if isinstance(need_value, int) and isinstance(capacity_value, int):
                if need_value == capacity_value == 0:
                    continue
                elif need_value > capacity_value:
                    needs_line[i] = f"{BColors.FAIL}{need_value}{BColors.ENDC}"
                    capacity_line[i] = f"{BColors.FAIL}{capacity_value}{BColors.ENDC}"
                elif need_value == capacity_value:
                    needs_line[i] = f"{BColors.WARNING}{need_value}{BColors.ENDC}"
                    capacity_line[i] = (
                        f"{BColors.WARNING}{capacity_value}{BColors.ENDC}"
                    )

    def draw(self):
        start_day, time_span_days = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        # days
        days = list(range(time_span_days))
        start_date = datetime.date.fromisoformat(start_day)

        # weekend line data
        is_we = []
        for day in days:
            iso_day = start_date + datetime.timedelta(days=day)
            if iso_day.weekday() in [5, 6]:
                is_we.append("X")
            else:
                is_we.append("")

        # header block
        self.draw_indented_list([""] + days)
        self.draw_indented_list([""] + is_we)
        self.draw_sep(len(days) * self.day_width + self.block_width)

        # needs & capacities
        total_needs_data = [0] * len(days)
        total_capacity_people = [[]] * len(days)

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

            needs_data = [f"{shift_id} needs"]
            capacities_data = [f"{shift_id} capacity"]

            for i, day in enumerate(days):
                # estimate minimal coverage needed for this shift for this day
                needs_count = sum(
                    [
                        value[0]
                        for value in self.db_adapter.select(
                            "coverage",
                            ["min_value"],
                            f"shift_id='{shift_id}' AND day={day}",
                        )
                    ]
                )
                needs_data.append(needs_count)
                total_needs_data[i] += needs_count

                # estimate count of available person to cover for this shift for this day
                statement = f"""
                SELECT person_id from coverage_person
                INNER JOIN coverage on coverage_person.coverage_id=coverage.id
                WHERE coverage.shift_id='{shift_id}'
                AND day={day}
                GROUP BY person_id
                """
                capacity = 0
                for person_data in self.db_adapter.cur.execute(statement).fetchall():
                    # check if person is available for this day
                    person_id = person_data[0]

                    # ignore person if preallocated on another shift or not working
                    is_preallocated = self.db_adapter.select(
                        "preallocation",
                        ["id"],
                        f"person_id='{person_id}' and day={day} and (type!=2 or shift_id!='{shift_id}')",
                    )

                    # ignore person if excluded for this day and shift
                    is_excluded = self.db_adapter.select(
                        "exclusion",
                        ["id"],
                        f"person_id='{person_id}' and day={day} and shift_id='{shift_id}'",
                    )

                    if not is_preallocated and not is_excluded:
                        capacity += 1
                        if person_id not in total_capacity_people[day]:
                            total_capacity_people[day].append(person_id)

                capacities_data.append(capacity)

            if sum(needs_data[1:]) or sum(capacities_data[1:]):
                # ignore line if no data
                #                self.colorize(needs_data, capacities_data)  # TODO: find a solution that don't break indentation
                self.draw_indented_list(needs_data)
                self.draw_indented_list(capacities_data)
                self.draw_sep(len(days) * self.day_width + self.block_width)

        # draw totals
        #        self.colorize(total_needs_data, total_capacity_people)
        self.draw_indented_list(["total needs"] + total_needs_data)
        self.draw_indented_list(
            ["total capacity"]
            + [len(people_capacity) for people_capacity in total_capacity_people]
        )
        self.draw_sep(len(days) * self.day_width + self.block_width)
